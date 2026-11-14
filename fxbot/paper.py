"""Paper trading for the FX trend strategy. Simulated money only, no broker, no API keys.

Run once per weekday after the daily close (the GitHub workflow runs at 00:30 UTC Tue-Sat):
    python -m fxbot paper run

Each run:
  1. downloads CLOSED daily bars for every pair (enough for the 200-day SMA),
  2. marks open positions to the latest quote and charges financing for the time held,
  3. on a new signal day, computes each pair's blend, applies the same no-trade band as
     the backtest (strategy.band_step) against the last signal, and resizes only pairs
     whose banded signal changed,
  4. fills at the latest quote, charging half the spread + slippage from config.toml.
     (FX has no free public order book, so unlike the crypto bot this is a cost model,
     not a walk of real book depth),
  5. appends fills / equity / a run log to paper/ (committed to git by the workflow).

Running it twice for the same signal day doesn't trade twice; it only re-marks.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable


from . import data as D
from .config import pair_cost, pair_symbols
from .strategy import band_step, realized_vol, rule_weights, vol_scale

MIN_TRADE_USD = 50.0


@dataclass
class State:
    started: str
    initial_capital: float
    balance: float                       # USD equity: cash plus marked P&L of open positions
    units: dict = field(default_factory=dict)        # signed base-currency units per pair
    mark: dict = field(default_factory=dict)         # price positions were last marked at
    signal: dict = field(default_factory=dict)       # last banded signal per pair
    last_signal_day: str | None = None
    last_run: str | None = None
    costs_paid: float = 0.0
    financing_paid: float = 0.0

    @classmethod
    def load(cls, d: Path) -> "State | None":
        f = d / "state.json"
        return cls(**json.loads(f.read_text())) if f.exists() else None

    def save(self, d: Path) -> None:
        d.mkdir(parents=True, exist_ok=True)
        (d / "state.json").write_text(json.dumps(asdict(self), indent=1))


def base_quote(pair: str) -> tuple[str, str]:
    b, q = pair.split("/")
    return b, q


def usd_per_base(pair: str, px: float) -> float:
    """USD value of one unit of the base currency."""
    b, q = base_quote(pair)
    if q == "USD":
        return px
    if b == "USD":
        return 1.0
    raise ValueError(f"{pair}: only pairs against USD are supported")


def usd_per_quote(pair: str, px: float) -> float:
    b, q = base_quote(pair)
    return 1.0 if q == "USD" else 1.0 / px


def notional_usd(pair: str, units: float, px: float) -> float:
    return units * usd_per_base(pair, px)


def _append_csv(path: Path, row: dict) -> None:
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def run_daily(cfg: dict, state_dir: Path, now: datetime | None = None,
              load_closes: Callable = D.load_closes, latest_price: Callable = D.latest_price) -> dict:
    now = now or datetime.now(timezone.utc)
    state_dir.mkdir(parents=True, exist_ok=True)
    st_cfg, sz = cfg["strategy"], cfg["sizing"]
    mode = st_cfg["mode"]
    pairs = list(cfg["pairs"])
    syms = pair_symbols(cfg)
    st = State.load(state_dir) or State(started=now.isoformat(timespec="seconds"),
                                        initial_capital=float(cfg["paper"]["initial_capital"]),
                                        balance=float(cfg["paper"]["initial_capital"]))
    for p in pairs:
        st.units.setdefault(p, 0.0)
        st.signal.setdefault(p, 0.0)

    start = (now - timedelta(days=550)).strftime("%Y-%m-%d")
    closes = load_closes(syms, start=start, now=now)
    signal_day = str(closes.index[-1].date())
    px = {p: float(latest_price(syms[p])) for p in pairs}

    # 1) mark to market + financing since the last run
    for p in pairs:
        if st.units[p] and p in st.mark:
            st.balance += st.units[p] * (px[p] - st.mark[p]) * usd_per_quote(p, px[p])
        st.mark[p] = px[p]
    if st.last_run:
        days = (now - datetime.fromisoformat(st.last_run)).total_seconds() / 86_400
        gross = sum(abs(notional_usd(p, st.units[p], px[p])) for p in pairs)
        fin = gross * cfg["costs"]["financing_bps_year"] / 1e4 / 365 * max(days, 0)
        st.balance -= fin
        st.financing_paid += fin
    st.last_run = now.isoformat(timespec="seconds")

    # 2) signals on the latest closed day
    raw, banded, fills = {}, {}, []
    acted = st.last_signal_day == signal_day
    for p in pairs:
        c = closes[p].dropna()
        raw[p] = float(rule_weights(c, "blend", mode, tuple(st_cfg["sma"]), tuple(st_cfg["mom"])).iloc[-1])
        banded[p] = band_step(raw[p], st.signal[p], st_cfg["band"], mode)

    if not acted:
        equity = st.balance
        weights = {p: notional_usd(p, st.units[p], px[p]) / equity for p in pairs}
        changed = [p for p in pairs if banded[p] != st.signal[p]]
        for p in changed:
            vol = float(realized_vol(closes[p].dropna(), sz["vol_lookback"]).iloc[-1])
            weights[p] = banded[p] * vol_scale(vol, len(pairs), sz)
        gross = sum(abs(w) for w in weights.values())
        if gross > sz["max_gross_leverage"]:
            weights = {p: w * sz["max_gross_leverage"] / gross for p, w in weights.items()}
            changed = pairs
        for p in changed:
            target_units = weights[p] * equity / usd_per_base(p, px[p])
            delta = target_units - st.units[p]
            traded_usd = abs(notional_usd(p, delta, px[p]))
            st.signal[p] = banded[p]
            if traded_usd < MIN_TRADE_USD:
                continue
            cost = traded_usd * pair_cost(cfg, p)
            st.units[p] = target_units
            st.balance -= cost
            st.costs_paid += cost
            fill = {"time": st.last_run, "signal_day": signal_day, "pair": p,
                    "side": "buy" if delta > 0 else "sell", "units": round(abs(delta), 2),
                    "price": px[p], "notional_usd": round(traded_usd, 2), "cost_usd": round(cost, 2),
                    "signal": round(banded[p], 4), "target_weight": round(weights[p], 4)}
            fills.append(fill)
            _append_csv(state_dir / "fills.csv", fill)
        st.last_signal_day = signal_day

    equity = st.balance
    gross = sum(abs(notional_usd(p, st.units[p], px[p])) for p in pairs)
    snap = {"time": st.last_run, "signal_day": signal_day, "equity": round(equity, 2),
            "gross_leverage": round(gross / equity, 3) if equity else 0,
            **{f"{p.replace('/', '')}_px": px[p] for p in pairs},
            **{f"{p.replace('/', '')}_sig": round(st.signal[p], 4) for p in pairs},
            **{f"{p.replace('/', '')}_w": round(notional_usd(p, st.units[p], px[p]) / equity, 4)
               for p in pairs}}
    if not acted:
        _append_csv(state_dir / "equity.csv", snap)
    st.save(state_dir)
    line = (f"- {st.last_run} signal {signal_day}: equity ${equity:,.2f} "
            f"({(equity / st.initial_capital - 1) * 100:+.2f}%), gross {snap['gross_leverage']:.2f}x; "
            + (f"{len(fills)} fill(s): " + "; ".join(
                f"{f['side']} {f['units']:,.0f} {f['pair']} @ {f['price']}" for f in fills)
               if fills else "no trades")
            + (" (already processed, re-marked only)" if acted else ""))
    with open(state_dir / "RUNS.md", "a") as f:
        f.write(line + "\n")
    return {"snapshot": snap, "fills": fills, "already_processed": acted, "log": line,
            "raw": raw, "banded": banded}


def status(cfg: dict, state_dir: Path) -> str:
    st = State.load(state_dir)
    if not st:
        return "No paper account yet. Run: python -m fxbot paper run"
    lines = [f"PAPER account since {st.started} (start ${st.initial_capital:,.2f})",
             f"equity ${st.balance:,.2f} ({(st.balance / st.initial_capital - 1) * 100:+.2f}%), "
             f"trading costs ${st.costs_paid:,.2f}, financing ${st.financing_paid:,.2f}",
             f"last signal day {st.last_signal_day}"]
    for p in cfg["pairs"]:
        u = st.units.get(p, 0.0)
        side = "long" if u > 0 else "short" if u < 0 else "flat"
        lines.append(f"  {p}: signal {st.signal.get(p, 0):+.2f}, {side} {abs(u):,.0f} {p.split('/')[0]}")
    return "\n".join(lines)
