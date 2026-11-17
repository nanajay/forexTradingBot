"""Mirror a paper account onto an OANDA PRACTICE account (demo money, real broker prices).

The paper accounts (paper/ for the trend rules, paper_ml/ for the learning model) decide the
positions. Each run, this module:
  1. reads that paper account's current positions as weights (notional / equity, signed),
  2. reads the practice account's NAV, positions and live bid/ask from OANDA,
  3. sizes the same weights to the practice NAV and sends market orders for the differences,
  4. re-reads positions and records any mismatch, plus fills, real spreads and financing,
     so broker reality can be compared with the paper accounts' cost assumptions.

Safety checks (the same kind of rails as a real-money bot, so they are tested before ever mattering):
  * market closed / instrument not tradeable    -> no orders that run
  * paper account not updated in the last 36 h   -> no orders (stale decisions)
  * broker mid more than 3% from the paper price -> skip that pair (bad data)
  * spread wider than max_spread_bps            -> skip that pair
  * target gross leverage above max_gross       -> no orders at all
  * single order above max_order_x_nav x NAV     -> skip that order
  * NAV below halt_nav_fraction of starting NAV  -> halt, no orders until reset by hand
  * small changes (<10% of the position, or < $50) are not traded, to avoid churn
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .oanda import OandaPractice, instrument
from .paper import notional_usd, usd_per_base

DEFAULTS = {"max_spread_bps": 10.0, "max_deviation": 0.03, "max_gross": 4.5, "max_order_x_nav": 3.0,
            "halt_nav_fraction": 0.5, "min_trade_usd": 50.0, "rebalance_threshold": 0.10,
            "max_state_age_hours": 36.0}


def _append_csv(path: Path, row: dict) -> None:
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def usd_per_unit(ccy: str, prices: dict[str, dict]) -> float:
    """USD value of one unit of the account currency, from live OANDA mids."""
    if ccy == "USD":
        return 1.0
    if f"{ccy}_USD" in prices:
        return prices[f"{ccy}_USD"]["mid"]
    if f"USD_{ccy}" in prices:
        return 1.0 / prices[f"USD_{ccy}"]["mid"]
    raise RuntimeError(f"account currency {ccy}: no {ccy}/USD price available to convert NAV")


def paper_weights(state_dir: Path, pairs: list[str]) -> tuple[dict[str, float], dict[str, float], str]:
    """Signed weight (notional / equity) and mark price per pair from a paper account's state."""
    st = json.loads((state_dir / "state.json").read_text())
    bal = float(st["balance"])
    marks = {p: float(st["mark"][p]) for p in pairs if p in st.get("mark", {})}
    w = {p: notional_usd(p, float(st["units"].get(p, 0.0)), marks[p]) / bal if p in marks and bal > 0 else 0.0
         for p in pairs}
    return w, marks, st.get("last_run") or ""


def plan_orders(weights: dict[str, float], marks: dict[str, float], nav: float, positions: dict[str, float],
                prices: dict[str, dict], rails: dict) -> tuple[list[dict], list[dict]]:
    """Return (orders, skipped). `nav` is in USD. Pure function: no I/O, so it is unit-tested directly."""
    orders, skipped = [], []
    gross = sum(abs(v) for v in weights.values())
    if gross > rails["max_gross"]:
        return [], [{"pair": "*", "reason": f"target gross {gross:.2f}x above {rails['max_gross']}x"}]
    for p, w in weights.items():
        inst = instrument(p)
        q = prices.get(inst)
        if not q or not q["tradeable"]:
            skipped.append({"pair": p, "reason": "not tradeable (market closed?)"})
            continue
        mid = q["mid"]
        spread_bps = (q["ask"] - q["bid"]) / mid * 1e4
        if spread_bps > rails["max_spread_bps"]:
            skipped.append({"pair": p, "reason": f"spread {spread_bps:.1f} bps"})
            continue
        if p in marks and abs(mid / marks[p] - 1) > rails["max_deviation"]:
            skipped.append({"pair": p, "reason": f"broker {mid} vs paper {marks[p]} (bad data?)"})
            continue
        target = int(round(w * nav / usd_per_base(p, mid)))
        cur = int(round(positions.get(inst, 0.0)))
        delta = target - cur
        if delta == 0:
            continue
        delta_usd = abs(notional_usd(p, delta, mid))
        big = max(abs(target), abs(cur))
        must = (target == 0) or (cur != 0 and (target > 0) != (cur > 0)) or cur == 0
        if not must and (abs(delta) < rails["rebalance_threshold"] * big):
            continue
        if delta_usd < rails["min_trade_usd"]:
            continue
        if delta_usd > rails["max_order_x_nav"] * nav:
            skipped.append({"pair": p, "reason": f"order ${delta_usd:,.0f} above {rails['max_order_x_nav']}x NAV"})
            continue
        orders.append({"pair": p, "instrument": inst, "units": delta, "target": target, "current": cur,
                       "mid": mid, "bid": q["bid"], "ask": q["ask"], "spread_bps": round(spread_bps, 2)})
    return orders, skipped


def place_with_safe_retry(client, account: str, o: dict, strategy: str, wait_s: float = 5.0) -> dict:
    """Place a market order. If OANDA answers 401 (the passing authorization error it sometimes gives
    a valid token), retry ONCE, and only after re-reading the account confirms the position is
    unchanged, i.e. the first attempt placed nothing. Any other error is not retried."""
    import time as _time
    try:
        return client.market_order(account, o["instrument"], o["units"], tag=f"fxbot-{strategy}")
    except Exception as e:
        if "-> 401" not in str(e):
            raise
        _time.sleep(wait_s)
        held = int(round(client.positions(account).get(o["instrument"], 0.0)))
        if held != o["current"]:
            raise RuntimeError(f"{e} (position changed to {held}: not retrying)") from e
        return client.market_order(account, o["instrument"], o["units"], tag=f"fxbot-{strategy}-retry")


def run(cfg: dict, strategy: str, paper_dir: Path, out_dir: Path, account: str,
        client: OandaPractice | None = None, now: datetime | None = None, dry_run: bool = False) -> dict:
    now = now or datetime.now(timezone.utc)
    rails = {**DEFAULTS, **cfg.get("practice", {})}
    client = client or OandaPractice()
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = list(cfg["pairs"])
    stamp = now.isoformat(timespec="seconds")
    st_file = out_dir / "state.json"
    st = json.loads(st_file.read_text()) if st_file.exists() else {}

    summ = client.summary(account)
    nav = float(summ["NAV"])
    if not st:
        st = {"strategy": strategy, "account": account[-4:], "currency": summ.get("currency", "USD"),
              "started": stamp, "start_nav": nav, "halted": False}
    positions = client.positions(account)
    prices = client.pricing(account, [instrument(p) for p in pairs])
    weights, marks, paper_last = paper_weights(paper_dir, pairs)
    ccy = summ.get("currency", "USD")
    nav_usd = nav * usd_per_unit(ccy, prices)              # e.g. a GBP account: NAV x GBP/USD

    orders, skipped, fills = [], [], []
    reason = None
    if st.get("halted"):
        reason = "HALTED earlier (NAV fell below the halt level); reset practice state by hand to resume"
    elif nav < rails["halt_nav_fraction"] * st["start_nav"]:
        st["halted"] = True
        reason = f"HALT: NAV {nav:,.2f} below {rails['halt_nav_fraction']:.0%} of start {st['start_nav']:,.2f}"
    elif not paper_last or (now - datetime.fromisoformat(paper_last)).total_seconds() / 3600 > rails["max_state_age_hours"]:
        reason = f"paper account not updated recently (last run {paper_last or 'never'})"
    else:
        orders, skipped = plan_orders(weights, marks, nav_usd, positions, prices, rails)

    for o in orders:
        row = {"time": stamp, "pair": o["pair"], "units": o["units"], "target": o["target"],
               "mid_before": o["mid"], "spread_bps": o["spread_bps"]}
        if dry_run:
            row.update(status="dry-run")
        else:
            try:
                resp = place_with_safe_retry(client, account, o, strategy)
                fill = resp.get("orderFillTransaction")
                if fill:
                    px = float(fill["price"])
                    side = 1 if o["units"] > 0 else -1
                    row.update(status="filled", price=px,
                               slippage_vs_mid_bps=round((px / o["mid"] - 1) * 1e4 * side, 2),
                               half_spread_cost=float(fill.get("halfSpreadCost", 0) or 0),
                               financing=float(fill.get("financing", 0) or 0), pl=float(fill.get("pl", 0) or 0))
                else:
                    cancel = resp.get("orderCancelTransaction", {})
                    row.update(status="rejected", reason=cancel.get("reason", "unknown"))
            except Exception as e:                        # one failed order must not stop the others
                row.update(status="error", reason=str(e)[:200])
        fills.append(row)
        _append_csv(out_dir / "fills.csv", {k: row.get(k, "") for k in
                    ("time", "pair", "units", "target", "mid_before", "spread_bps", "status", "price",
                     "slippage_vs_mid_bps", "half_spread_cost", "financing", "pl", "reason")})

    # reconcile: what the broker holds vs what we aimed for
    mismatches = []
    if orders and not dry_run:
        after = client.positions(account)
        for o in orders:
            held = int(round(after.get(o["instrument"], 0.0)))
            if held != o["target"]:
                mismatches.append({"pair": o["pair"], "target": o["target"], "held": held})
        summ = client.summary(account)
        nav = float(summ["NAV"])
        nav_usd = nav * usd_per_unit(ccy, prices)
        positions = after
    gross = sum(abs(notional_usd(p, positions.get(instrument(p), 0.0), prices[instrument(p)]["mid"]))
                for p in pairs if instrument(p) in prices) / nav_usd if nav_usd else 0.0
    _append_csv(out_dir / "equity.csv", {
        "time": stamp, "nav": round(nav, 2), "balance": round(float(summ.get("balance", 0)), 2),
        "unrealized_pl": round(float(summ.get("unrealizedPL", 0)), 2),
        "financing_total": round(float(summ.get("financing", 0) or 0), 2),
        "margin_used": round(float(summ.get("marginUsed", 0)), 2), "gross_leverage": round(gross, 3),
        "orders": len(orders), "filled": sum(f.get("status") == "filled" for f in fills)})
    st["last_run"] = stamp
    st_file.write_text(json.dumps(st, indent=1))
    line = (f"- {stamp} [{strategy}{' dry-run' if dry_run else ''}] NAV {nav:,.2f} {ccy} "
            f"({(nav / st['start_nav'] - 1) * 100:+.2f}% since {st['started'][:10]}), gross {gross:.2f}x; "
            + (reason if reason else f"{len(orders)} order(s), "
               f"{sum(f.get('status') == 'filled' for f in fills)} filled")
            + (f"; skipped: {skipped}" if skipped else "") + (f"; MISMATCH: {mismatches}" if mismatches else ""))
    with open(out_dir / "RUNS.md", "a") as f:
        f.write(line + "\n")
    return {"log": line, "orders": orders, "fills": fills, "skipped": skipped,
            "mismatches": mismatches, "reason": reason}


def status(out_dir: Path, cfg: dict) -> str:
    import pandas as pd
    if not (out_dir / "state.json").exists():
        return f"No practice runs yet in {out_dir}"
    st = json.loads((out_dir / "state.json").read_text())
    eq = pd.read_csv(out_dir / "equity.csv")
    last = eq.iloc[-1]
    lines = [f"OANDA PRACTICE [{st['strategy']}] account …{st['account']} since {st['started']}"
             f" (start NAV {st['start_nav']:,.2f} {st.get('currency', 'USD')})"
             f"{' HALTED' if st.get('halted') else ''}",
             f"NAV {last.nav:,.2f} ({(last.nav / st['start_nav'] - 1) * 100:+.2f}%), "
             f"financing so far {last.financing_total:,.2f}, gross {last.gross_leverage:.2f}x"]
    if (out_dir / "fills.csv").exists():
        f = pd.read_csv(out_dir / "fills.csv")
        ok = f[f.status == "filled"]
        if len(ok):
            assumed = {p: v[1] / 2 + cfg["costs"]["slippage_bps"] for p, v in cfg["pairs"].items()}
            lines.append(f"{len(ok)} fills: real cost vs mid {ok.slippage_vs_mid_bps.mean():.2f} bps on average "
                         f"(paper assumes {sum(assumed.values()) / len(assumed):.2f} bps); "
                         f"{(f.status != 'filled').sum()} not filled")
    return "\n".join(lines)


def mask(account_id: str) -> str:
    """Show only the last 7 characters (e.g. '…814-001'): enough to tell accounts apart in public logs."""
    return "…" + account_id[-7:] if account_id else "(not set)"


def check(client: OandaPractice, accounts: dict[str, str], instruments: list[str]) -> str:
    """Test each OANDA request the bot needs, per configured account. Read-only: places no orders."""
    lines = []
    try:
        listed = client.accounts()
        ids = [a["id"] for a in listed]
        lines.append(f"token OK: it can reach {len(ids)} account(s): " + ", ".join(mask(i) for i in ids))
    except Exception as e:
        return f"token FAILED on account list: {e}"
    for name, acc in accounts.items():
        if not acc:
            lines.append(f"[{name}] account not set")
            continue
        lines.append(f"[{name}] {mask(acc)}: {'listed for this token' if acc in ids else 'NOT among the token accounts'}")
        for label, fn in (("summary", lambda: client.summary(acc)),
                          ("positions", lambda: client.positions(acc)),
                          ("pricing", lambda: client.pricing(acc, instruments))):
            try:
                out = fn()
                extra = ""
                if label == "summary":
                    extra = f" (currency {out.get('currency')}, NAV {float(out['NAV']):,.2f})"
                lines.append(f"    {label}: OK{extra}")
            except Exception as e:
                lines.append(f"    {label}: FAILED {str(e)[:160]}")
    return "\n".join(lines)
