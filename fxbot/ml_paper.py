"""Paper trading driven by the learning model (fxbot/model.py). Simulated money only.

Runs alongside the trend paper account (paper/) so the two can be compared on live data.
Once per week, on the first run after a Friday close:
  1. downloads full history: FX closes, interest rates (FRED), VIX and S&P 500,
  2. rebuilds the weekly feature panel and RETRAINS the model on every week whose outcome is
     already known (so it keeps learning as new weeks arrive),
  3. predicts next week's relative return for each of the 7 currencies,
  4. goes long the 3 best-predicted and short the 3 worst (dollar-neutral), scaled to 10% volatility,
  5. logs every prediction to predictions.csv, and scores earlier predictions once their week is over,
     so the live hit rate / IC can be compared with the backtest (IC about 0.00 out of sample).
Every run (also mid-week) marks positions to market and accrues interest carry minus financing.

The model, target and portfolio rules are the ones tested in results/MODEL.md: LightGBM on the
relative target. They are fixed; don't change them based on a few weeks of live results.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from . import data as D
from . import factors as F
from . import model as M
from .config import pair_cost, pair_symbols
from .paper import _append_csv, notional_usd, usd_per_base, usd_per_quote
from .rates import monthly_rates, usable_rates
from .strategy import DAYS_PER_YEAR

MODEL_KIND = "lgbm"
TARGET = "y_rel"
VOL_TARGET = 0.10
COV_LOOKBACK = 120
MAX_GROSS = 4.0
MIN_TRADE_USD = 50.0
PAIR_OF = {v: k for k, v in F.CCY_OF.items()}           # "EUR" -> "EUR/USD"


@dataclass
class MLState:
    started: str
    initial_capital: float
    balance: float
    units: dict = field(default_factory=dict)
    mark: dict = field(default_factory=dict)
    last_signal_day: str | None = None
    last_run: str | None = None
    costs_paid: float = 0.0
    financing_paid: float = 0.0
    carry_earned: float = 0.0
    weeks_traded: int = 0

    @classmethod
    def load(cls, d: Path) -> "MLState | None":
        f = d / "state.json"
        return cls(**json.loads(f.read_text())) if f.exists() else None

    def save(self, d: Path) -> None:
        (d / "state.json").write_text(json.dumps(asdict(self), indent=1))


def default_loaders(cfg: dict) -> dict[str, Callable]:
    syms = pair_symbols(cfg)
    return {
        "closes": lambda now: D.load_closes(syms, start="2003-01-01", now=now),
        "rates": lambda: usable_rates(monthly_rates()),
        "market": lambda now: (D.daily_closes("^VIX", "2003-01-01", now),
                               D.daily_closes("^GSPC", "2003-01-01", now)),
        "price": D.latest_price,
    }


def target_exposures(pred: pd.Series, rets: pd.DataFrame) -> pd.Series:
    """Long top 3 / short bottom 3 predicted currencies, scaled to VOL_TARGET (ex-ante)."""
    rank = pred.rank(ascending=False, method="first")
    w = pd.Series(0.0, index=pred.index)
    w[rank <= 3] = 1 / 3
    w[rank > len(pred) - 3] = -1 / 3
    cov = rets[w.index].iloc[-COV_LOOKBACK:].fillna(0.0).cov().to_numpy() * DAYS_PER_YEAR
    v = math.sqrt(max(w.to_numpy() @ cov @ w.to_numpy(), 0.0))
    w = w * (VOL_TARGET / v if v > 1e-9 else 0.0)
    gross = w.abs().sum()
    return w * (MAX_GROSS / gross) if gross > MAX_GROSS else w


def train_and_predict(panel: pd.DataFrame) -> tuple[pd.Series, pd.Timestamp, pd.Series, int]:
    cols = M.feature_cols(panel)
    signal_date = panel["date"].max()
    train = panel[panel[TARGET].notna() & (panel["date"] < signal_date)].dropna(subset=cols)
    latest = panel[panel["date"] == signal_date]
    m = M.make_model(MODEL_KIND)
    m.fit(train[cols].to_numpy(), train[TARGET].clip(-4, 4).to_numpy())
    pred = pd.Series(m.predict(latest[cols].to_numpy()), index=latest["ccy"].to_numpy())
    imp = pd.Series(m.feature_importances_, index=cols).sort_values(ascending=False)
    return pred, signal_date, imp, len(train)


def run(cfg: dict, state_dir: Path, now: datetime | None = None, loaders: dict | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    loaders = loaders or default_loaders(cfg)
    state_dir.mkdir(parents=True, exist_ok=True)
    syms = pair_symbols(cfg)
    pairs = list(cfg["pairs"])
    st = MLState.load(state_dir) or MLState(started=now.isoformat(timespec="seconds"),
                                            initial_capital=float(cfg["paper"]["initial_capital"]),
                                            balance=float(cfg["paper"]["initial_capital"]))
    for p in pairs:
        st.units.setdefault(p, 0.0)

    closes = loaders["closes"](now)
    px = F.ccy_prices(closes)
    rates = loaders["rates"]()
    diff = F.rate_diff(rates, px.index, list(px.columns))
    vix, spx = loaders["market"](now)
    live = {p: float(loaders["price"](syms[p])) for p in pairs}

    # 1) mark to market, carry and financing since the last run
    days = 0.0
    if st.last_run:
        days = max((now - datetime.fromisoformat(st.last_run)).total_seconds() / 86_400, 0.0)
    cur_diff = diff.iloc[-1]
    for p in pairs:
        u = st.units[p]
        if u and p in st.mark:
            st.balance += u * (live[p] - st.mark[p]) * usd_per_quote(p, live[p])
        if u and days:
            ccy = F.CCY_OF[p]
            expo_usd = u * usd_per_base(p, live[p]) * (1 if p.endswith("/USD") else -1)  # + = long ccy
            carry = expo_usd * float(cur_diff[ccy]) * days / 365
            fin = abs(notional_usd(p, u, live[p])) * cfg["costs"]["financing_bps_year"] / 1e4 * days / 365
            st.balance += carry - fin
            st.carry_earned += carry
            st.financing_paid += fin
        st.mark[p] = live[p]
    st.last_run = now.isoformat(timespec="seconds")

    # 2) weekly: retrain, predict, rebalance
    panel = M.build_panel(px, diff, vix, spx)
    signal_day = str(panel["date"].max().date())
    fills, info = [], {}
    acted = st.last_signal_day == signal_day
    if not acted:
        pred, sd, imp, n_train = train_and_predict(panel)
        rets = px.pct_change()
        expo = target_exposures(pred, rets)
        equity = st.balance
        for ccy, w in expo.items():
            p = PAIR_OF[ccy]
            sign = 1 if p.endswith("/USD") else -1          # long EUR = long EUR/USD; long JPY = short USD/JPY
            target_units = sign * w * equity / usd_per_base(p, live[p])
            delta = target_units - st.units[p]
            traded = abs(notional_usd(p, delta, live[p]))
            if traded < MIN_TRADE_USD:
                continue
            cost = traded * pair_cost(cfg, p)
            st.units[p] = target_units
            st.balance -= cost
            st.costs_paid += cost
            fill = {"time": st.last_run, "signal_day": signal_day, "pair": p,
                    "side": "buy" if delta > 0 else "sell", "units": round(abs(delta), 2),
                    "price": live[p], "notional_usd": round(traded, 2), "cost_usd": round(cost, 2),
                    "ccy_exposure": round(w, 4)}
            fills.append(fill)
            _append_csv(state_dir / "fills.csv", fill)
        for ccy in pred.index:
            _append_csv(state_dir / "predictions.csv",
                        {"signal_day": signal_day, "ccy": ccy, "pred": round(float(pred[ccy]), 5),
                         "rank": int(pred.rank(ascending=False)[ccy]), "exposure": round(float(expo[ccy]), 4),
                         "trained_on_weeks": n_train // len(pred)})
        imp.head(10).to_frame("importance").to_csv(state_dir / "feature_importance.csv")
        st.last_signal_day = signal_day
        st.weeks_traded += 1
        info = {"n_train_rows": n_train, "pred": pred.round(4).to_dict(), "exposure": expo.round(3).to_dict()}

    score_predictions(state_dir, panel)
    equity = st.balance
    gross = sum(abs(notional_usd(p, st.units[p], live[p])) for p in pairs)
    snap = {"time": st.last_run, "signal_day": signal_day, "equity": round(equity, 2),
            "gross_leverage": round(gross / equity, 3) if equity else 0,
            **{f"{F.CCY_OF[p]}_expo": round(st.units[p] * usd_per_base(p, live[p]) *
                                            (1 if p.endswith('/USD') else -1) / equity, 4) for p in pairs}}
    _append_csv(state_dir / "equity.csv", snap)
    st.save(state_dir)
    line = (f"- {st.last_run} week of {signal_day}: equity ${equity:,.2f} "
            f"({(equity / st.initial_capital - 1) * 100:+.2f}%), gross {snap['gross_leverage']:.2f}x; "
            + (f"retrained, {len(fills)} fill(s)" if not acted else "marked only"))
    with open(state_dir / "RUNS.md", "a") as f:
        f.write(line + "\n")
    return {"log": line, "already_processed": acted, "fills": fills, **info}


def score_predictions(state_dir: Path, panel: pd.DataFrame) -> None:
    """Fill in the realized relative return for predictions whose week has finished."""
    f = state_dir / "predictions.csv"
    if not f.exists():
        return
    preds = pd.read_csv(f)
    real = panel[["date", "ccy", TARGET]].dropna().copy()
    real["signal_day"] = real["date"].dt.strftime("%Y-%m-%d")
    preds = preds.drop(columns=[c for c in ("realized",) if c in preds]).merge(
        real[["signal_day", "ccy", TARGET]].rename(columns={TARGET: "realized"}),
        on=["signal_day", "ccy"], how="left")
    preds.to_csv(f, index=False)


def live_scorecard(state_dir: Path) -> dict:
    f = state_dir / "predictions.csv"
    if not f.exists():
        return {"weeks_scored": 0}
    p = pd.read_csv(f).dropna(subset=["realized"])
    if p.empty:
        return {"weeks_scored": 0}
    ic = p.groupby("signal_day")[["pred", "realized"]].apply(
        lambda g: g["pred"].rank().corr(g["realized"].rank()))
    top = p[p["rank"] <= 3].groupby("signal_day")["realized"].mean()
    bot = p[p["rank"] >= 5].groupby("signal_day")["realized"].mean()
    spread = (top - bot).dropna()
    return {"weeks_scored": int(ic.notna().sum()), "mean_IC": round(float(ic.mean()), 4),
            "IC_t": round(float(ic.mean() / ic.std() * np.sqrt(ic.notna().sum())), 2) if ic.notna().sum() > 2 else None,
            "weeks_long_beat_short_%": round(float((spread > 0).mean() * 100), 1) if len(spread) else None}


def status(state_dir: Path) -> str:
    st = MLState.load(state_dir)
    if not st:
        return "No ML paper account yet. Run: python -m fxbot ml run"
    sc = live_scorecard(state_dir)
    return (f"ML PAPER account since {st.started} (start ${st.initial_capital:,.2f})\n"
            f"equity ${st.balance:,.2f} ({(st.balance / st.initial_capital - 1) * 100:+.2f}%), "
            f"weeks traded {st.weeks_traded}, costs ${st.costs_paid:,.2f}, financing ${st.financing_paid:,.2f}, "
            f"carry ${st.carry_earned:+,.2f}\nlive scorecard: {sc}")
