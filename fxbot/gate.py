"""Go-live gate: scores each strategy against fixed criteria, so the decision is mechanical.

    python -m fxbot gate        -> prints the verdict and writes results/GATE.md

A strategy is READY only if every check passes. A check that lacks enough data says WAIT.
Thresholds are in config.toml [gate]; set them before looking at results and don't loosen
them to get a pass.

Checks (each on the strategy's OANDA practice account, with its paper account for comparison):
  duration     practice account has run at least min_weeks
  edge         practice return after all costs > 0; for the learning model, also a live prediction
               IC that's positive with t-stat >= min_ic_t over the scored weeks
  costs        real average fill cost vs mid <= cost_ratio_max x the paper assumption, and
               real financing <= cost_ratio_max x the assumed financing (a net credit passes)
  agreement    practice and paper returns over the same dates differ by <= max_tracking_gap
  reliability  missed weekday runs <= max_missed_days, no position mismatches, no halt,
               rejected/errored orders <= max_order_problems
  drawdown     worst fall of the practice account no deeper than max_drawdown
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

GATE_DEFAULTS = {"min_weeks": 26, "min_ic_t": 2.0, "cost_ratio_max": 1.25, "max_tracking_gap": 0.03,
                 "max_missed_days": 3, "max_order_problems": 2, "max_drawdown": -0.20}
HOLIDAYS = {(12, 25), (1, 1)}          # FX is effectively shut; runs may legitimately see no trading


@dataclass
class Check:
    name: str
    status: str          # PASS / FAIL / WAIT
    detail: str


def _read(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else None


def missed_weekdays(times: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> list[str]:
    ran = set(pd.to_datetime(times, utc=True).dt.strftime("%Y-%m-%d"))
    days = pd.bdate_range(start.normalize(), end.normalize(), tz="UTC")
    return [d.strftime("%Y-%m-%d") for d in days
            if (d.month, d.day) not in HOLIDAYS and d.strftime("%Y-%m-%d") not in ran]


def max_drawdown(values: pd.Series) -> float:
    v = values.astype(float)
    return float((v / v.cummax() - 1).min()) if len(v) else 0.0


def live_ic(pred_file: Path) -> tuple[int, float | None, float | None]:
    p = _read(pred_file)
    if p is None or "realized" not in p:
        return 0, None, None
    p = p.dropna(subset=["realized"])
    if p.empty:
        return 0, None, None
    ic = p.groupby("signal_day")[["pred", "realized"]].apply(
        lambda g: g["pred"].rank().corr(g["realized"].rank())).dropna()
    if len(ic) < 3:
        return len(ic), float(ic.mean()) if len(ic) else None, None
    return len(ic), float(ic.mean()), float(ic.mean() / ic.std() * np.sqrt(len(ic)))


def evaluate(cfg: dict, root: Path, strategy: str, now: datetime | None = None) -> list[Check]:
    g = {**GATE_DEFAULTS, **cfg.get("gate", {})}
    now = now or datetime.now(timezone.utc)
    prac = root / f"practice_{strategy}"
    paper = root / ("paper" if strategy == "trend" else "paper_ml")
    st_file = prac / "state.json"
    eq = _read(prac / "equity.csv")
    if not st_file.exists() or eq is None or eq.empty:
        return [Check("practice data", "WAIT", "no OANDA practice runs recorded yet")]
    st = json.loads(st_file.read_text())
    eq["time"] = pd.to_datetime(eq["time"], utc=True)
    start, last = pd.Timestamp(st["started"]), eq["time"].iloc[-1]
    weeks = (last - start).days / 7
    nav0, nav1 = float(st["start_nav"]), float(eq["nav"].iloc[-1])
    ret = nav1 / nav0 - 1
    checks: list[Check] = []

    # duration
    checks.append(Check("duration", "PASS" if weeks >= g["min_weeks"] else "WAIT",
                        f"{weeks:.1f} of {g['min_weeks']} weeks"))

    # edge
    enough = weeks >= g["min_weeks"]
    edge_detail = f"practice return {ret * 100:+.2f}% after all costs"
    edge_ok = ret > 0
    if strategy == "ml":
        n, ic, t = live_ic(paper / "predictions.csv")
        edge_detail += f"; live IC {ic:+.3f} (t {t:.2f}) over {n} weeks" if ic is not None and t is not None \
            else f"; live IC: {n} week(s) scored"
        edge_ok = edge_ok and ic is not None and t is not None and ic > 0 and t >= g["min_ic_t"]
    checks.append(Check("edge", ("PASS" if edge_ok else "FAIL") if enough else "WAIT", edge_detail))

    # costs
    fills = _read(prac / "fills.csv")
    filled = fills[fills["status"] == "filled"] if fills is not None else None
    if filled is None or filled.empty:
        checks.append(Check("costs", "WAIT", "no filled practice orders yet"))
    else:
        assumed = {p: v[1] / 2 + cfg["costs"]["slippage_bps"] for p, v in cfg["pairs"].items()}
        a = filled["pair"].map(assumed).mean()
        real = filled["slippage_vs_mid_bps"].astype(float).mean()
        years = max((last - start).days / 365, 1 / 365)
        fin_real = -float(eq["financing_total"].iloc[-1])          # OANDA: negative = paid
        fin_assumed = (cfg["costs"]["financing_bps_year"] / 1e4 * eq["gross_leverage"].astype(float).mean()
                       * nav0 * years)
        fin_ok = fin_real <= g["cost_ratio_max"] * max(fin_assumed, 1e-9) or fin_real <= 0
        ok = real <= g["cost_ratio_max"] * a and fin_ok
        checks.append(Check("costs", "PASS" if ok else "FAIL",
                            f"fills {real:.2f} bps vs assumed {a:.2f} bps (max x{g['cost_ratio_max']}); "
                            f"financing paid {fin_real:,.2f} vs assumed {fin_assumed:,.2f} "
                            f"({len(filled)} fills)"))

    # agreement with the paper account over the same dates
    peq = _read(paper / "equity.csv")
    if peq is None or len(peq) < 2:
        checks.append(Check("agreement", "WAIT", "paper account has too little history"))
    else:
        peq["time"] = pd.to_datetime(peq["time"], utc=True)
        # by date: the paper step runs seconds before the practice step in the same workflow
        same = peq[peq["time"].dt.normalize() >= start.normalize()]
        if len(same) < 2:
            checks.append(Check("agreement", "WAIT", "not enough overlapping days yet"))
        else:
            pret = same["equity"].iloc[-1] / same["equity"].iloc[0] - 1
            gap = ret - pret
            checks.append(Check("agreement", "PASS" if abs(gap) <= g["max_tracking_gap"] else "FAIL",
                                f"practice {ret * 100:+.2f}% vs paper {pret * 100:+.2f}% "
                                f"(gap {gap * 100:+.2f} pts, max {g['max_tracking_gap'] * 100:.0f})"))

    # reliability
    missed = missed_weekdays(eq["time"], start, last)
    runs = (prac / "RUNS.md").read_text() if (prac / "RUNS.md").exists() else ""
    mism = runs.count("MISMATCH")
    problems = int(fills["status"].isin(["rejected", "error"]).sum()) if fills is not None else 0
    rel_ok = (len(missed) <= g["max_missed_days"] and mism == 0 and not st.get("halted")
              and problems <= g["max_order_problems"])
    checks.append(Check("reliability", "PASS" if rel_ok else "FAIL",
                        f"missed weekdays {len(missed)}{(' ' + ', '.join(missed[-5:])) if missed else ''}; "
                        f"mismatches {mism}; order problems {problems}; "
                        f"{'HALTED' if st.get('halted') else 'not halted'}"))

    # drawdown
    dd = max_drawdown(eq["nav"])
    checks.append(Check("drawdown", "PASS" if dd >= g["max_drawdown"] else "FAIL",
                        f"worst fall {dd * 100:.1f}% (limit {g['max_drawdown'] * 100:.0f}%)"))
    return checks


def verdict(checks: list[Check]) -> str:
    if any(c.status == "FAIL" for c in checks):
        return "NOT READY"
    if all(c.status == "PASS" for c in checks):
        return "READY"
    return "WAIT"


def report(cfg: dict, root: Path, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    names = {"trend": "Trend rules (crypto port)", "ml": "Learning model"}
    parts = [f"# Go-live gate\n\nUpdated {now:%Y-%m-%d %H:%M UTC}. A strategy is **READY** only when every "
             "check passes. **WAIT** means not enough data yet. Thresholds: `config.toml [gate]`. "
             "Even READY means only \"eligible for a tiny live trial\", never \"safe\".\n"]
    for s in ("trend", "ml"):
        checks = evaluate(cfg, root, s, now)
        v = verdict(checks)
        rows = "\n".join(f"| {c.name} | {c.status} | {c.detail} |" for c in checks)
        parts.append(f"## {names[s]}: **{v}**\n\n| Check | Status | Detail |\n|---|---|---|\n{rows}\n")
    md = "\n".join(parts)
    res = root / "results"
    res.mkdir(exist_ok=True)
    (res / "GATE.md").write_text(md)
    # remember the verdicts (committed) and flag a change for today's alert step (not committed)
    summary = "; ".join(l[3:].replace("**", "") for l in md.splitlines() if l.startswith("## "))
    last = res / ".last_gate"
    prev = last.read_text() if last.exists() else ""
    flag = res / ".gate_changed"
    if prev and prev != summary:
        flag.write_text(f"{prev}  ->  {summary}")
    elif flag.exists():
        flag.unlink()
    last.write_text(summary)
    return md
