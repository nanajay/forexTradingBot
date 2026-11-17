"""Readable report pages for GitHub, in the same style as the daily phone summary.

    python -m fxbot pages      (the workflow runs it after every weekday run)

Writes:
  REPORT.md            overview: both strategies at a glance, today's trades, go-live check
  paper/REPORT.md      📈 forex trend strategy: paper + OANDA practice side by side
  paper_ml/REPORT.md   🤖 forex learning model: the same, plus the live prediction scorecard
Each strategy page gets a chart (report_equity.svg) with the paper and practice accounts.
Only data already in the repo is used; nothing is downloaded.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .alerts import _csv, _dot, _money, _paper, _pct, _practice, trades_text
from .paper import notional_usd

STRATEGIES = {
    "trend": {"icon": "📈", "name": "Forex trend strategy", "paper": "paper", "practice": "practice_trend",
              "what": "Follows the trend of each of the 7 major currency pairs: 7 fixed signals per pair (price vs "
                      "its 20/50/100/200-day averages, 30/90/180-day momentum). Long when the trend is up, short "
                      "when it's down, sized to a 10% volatility target. Trades when a pair's signal changes."},
    "ml": {"icon": "🤖", "name": "Forex learning model", "paper": "paper_ml", "practice": "practice_ml",
           "what": "A LightGBM model retrained every week on 24 inputs per currency (momentum, trend, volatility, "
                   "interest rates, market mood). Each Monday it buys the 3 currencies it expects to be strongest "
                   "next week and sells the 3 weakest, with no net bet on the dollar, 10% volatility target."},
}
CCYS = ["EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
GATE_WORDS = {"WAIT": "⏳ waiting for data", "READY": "✅ ready for a small live trial", "NOT READY": "⛔ not ready"}
STATUS_ICON = {"PASS": "✅", "FAIL": "❌", "WAIT": "⏳"}
GATE_PLAIN = {"duration": "Long enough on OANDA practice", "edge": "Making money after costs",
              "costs": "Real costs close to the assumptions", "agreement": "Practice matches paper",
              "reliability": "Runs reliably (no misses, mismatches, halts)", "drawdown": "Losses stay limited",
              "practice data": "OANDA practice data"}


# ---------- small helpers ----------------------------------------------------------------------
def _cell_change(st: dict | None, key: str) -> str:
    if st is None:
        return "–"
    if key == "day":
        if st["day_pct"] is None:
            return "⚪ first day"
        return f"{_dot(st['day_pct'])} {_money(st['day_abs'], st['ccy'], signed=True)} ({_pct(st['day_pct'])})"
    return f"{_dot(st['total_pct'])} {_pct(st['total_pct'])}"


def holdings(root: Path, paper_dir: str) -> list[tuple[str, float]]:
    """(currency, exposure vs USD as a multiple of equity) from the paper account; + = betting it rises."""
    f = root / paper_dir / "state.json"
    if not f.exists():
        return []
    st = json.loads(f.read_text())
    bal = float(st.get("balance") or 0)
    out = []
    for pair, u in st.get("units", {}).items():
        mark = st.get("mark", {}).get(pair)
        if not u or not mark or bal <= 0:
            continue
        base, quote = pair.split("/")
        ccy = base if quote == "USD" else quote
        usd = notional_usd(pair, float(u), float(mark))
        out.append((ccy, (usd if quote == "USD" else -usd) / bal))
    order = {c: i for i, c in enumerate(CCYS)}
    return sorted(out, key=lambda x: order.get(x[0], 99))


def svg_lines(series: dict[str, pd.Series], title: str, width: int = 760, height: int = 280) -> str:
    """Dependency-free SVG chart of one or more '% since start' lines (indexed by date string)."""
    colors = ["#2563eb", "#ea580c", "#16a34a"]
    pad_l, pad_r, pad_t, pad_b = 64, 20, 36, 56
    dates = sorted(set().union(*[set(s.index) for s in series.values() if len(s)])) or ["–"]
    vals = [v for s in series.values() for v in s.to_numpy()]
    lo, hi = min(vals + [0.0]), max(vals + [0.0])
    if hi - lo < 0.2:
        lo, hi = lo - 0.1, hi + 0.1
    n = len(dates)
    pos = {d: i for i, d in enumerate(dates)}
    X = lambda i: pad_l + (width - pad_l - pad_r) * (i / max(n - 1, 1))
    Y = lambda v: pad_t + (height - pad_t - pad_b) * (1 - (v - lo) / (hi - lo))
    grid = "".join(
        f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#e5e7eb"/>'
        f'<text x="{pad_l - 8}" y="{Y(v) + 4:.1f}" font-size="11" text-anchor="end" fill="#6b7280">'
        f'{"0%" if v == 0 else f"{v:+.1f}%"}</text>'
        for v in sorted({lo, 0.0, hi}))
    lines, legend = "", ""
    for k, (name, s) in enumerate(series.items()):
        c = colors[k % len(colors)]
        if len(s) == 1:
            d = s.index[0]
            lines += f'<circle cx="{X(pos[d]):.1f}" cy="{Y(s.iloc[0]):.1f}" r="4" fill="{c}"/>'
        elif len(s) > 1:
            pts = " ".join(f"{X(pos[d]):.1f},{Y(v):.1f}" for d, v in s.items())
            lines += f'<polyline fill="none" stroke="{c}" stroke-width="2.5" points="{pts}"/>'
        legend += (f'<rect x="{pad_l + 170 * k}" y="{height - 15}" width="14" height="4" rx="2" fill="{c}"/>'
                   f'<text x="{pad_l + 170 * k + 20}" y="{height - 9}" font-size="12" fill="#374151">{name}</text>')
    base = height - pad_b + 18
    axis = (f'<text x="{pad_l}" y="{base}" font-size="11" fill="#6b7280">{dates[0]}</text>'
            + (f'<text x="{width - pad_r}" y="{base}" font-size="11" fill="#6b7280" text-anchor="end">{dates[-1]}</text>'
               if len(dates) > 1 else ""))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif">'
            f'<rect width="100%" height="100%" fill="#ffffff" rx="8"/>'
            f'<text x="{pad_l}" y="20" font-size="14" font-weight="600" fill="#111827">{title}</text>{grid}'
            f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="#9ca3af"/>'
            f'{lines}{axis}{legend}</svg>')


def _pct_series(df: pd.DataFrame | None, col: str, start: float) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    d = df.copy()
    d["day"] = pd.to_datetime(d["time"], utc=True).dt.strftime("%Y-%m-%d")
    last = d.groupby("day")[col].last().astype(float)
    return (last / start - 1) * 100


def _gate(cfg: dict, root: Path, key: str):
    from .gate import evaluate, verdict
    try:
        checks = evaluate(cfg, root, key)
        return checks, verdict(checks)
    except Exception as e:                       # a broken section never stops the page
        return [], f"unavailable ({type(e).__name__})"


# ---------- strategy page ----------------------------------------------------------------------
def strategy_page(cfg: dict, root: Path, key: str, now: datetime) -> str:
    s = STRATEGIES[key]
    today = now.strftime("%Y-%m-%d")
    pst, ptr = _paper(root, s["paper"], today)
    qst, qtr, note = _practice(root, s["practice"], today)
    pstate = json.loads((root / s["paper"] / "state.json").read_text()) if (root / s["paper"] / "state.json").exists() else {}
    qstate = json.loads((root / s["practice"] / "state.json").read_text()) if (root / s["practice"] / "state.json").exists() else {}

    def val(st):
        return f"**{_money(st['value'], st['ccy'])}**" if st else "not started"
    started_p = (pstate.get("started") or "")[:10] or "–"
    started_q = (qstate.get("started") or "")[:10] or "–"
    costs_p = pstate.get("costs_paid", pstate.get("fees_paid"))
    qccy = (qst or {}).get("ccy") or qstate.get("currency", "")
    qsym = {"USD": "$", "GBP": "£", "EUR": "€"}.get(qccy, qccy)
    out = [f"# {s['icon']} {s['name']}", "",
           f"Updated {now:%a %d %b %Y, %H:%M} UTC · **practice and simulated money only, no real trades**", "",
           f"> {s['what']}", "",
           "## At a glance", "",
           f"| | Paper (simulated $) | OANDA practice (demo{' ' + qsym if qsym else ''}) |",
           "|---|---:|---:|",
           f"| **Account value** | {val(pst)} | {val(qst)} |",
           f"| Today | {_cell_change(pst, 'day')} | {_cell_change(qst, 'day')} |",
           f"| Since start | {_cell_change(pst, 'total')} (since {started_p}) | {_cell_change(qst, 'total')} (since {started_q}) |"]
    if costs_p is not None:
        out.append(f"| Trading costs paid | {_money(float(costs_p), 'USD')} | in the OANDA fill prices |")
    checks, v = _gate(cfg, root, key)
    dur = next((c.detail for c in checks if c.name == "duration"), "")
    out.append(f"| Go-live check | {GATE_WORDS.get(v, v)} {f'({dur})' if dur else ''} | |")

    # holdings
    h = holdings(root, s["paper"])
    out.append("\n## What it's betting on\n")
    if h:
        out.append("Each position is a bet on a currency rising (↑) or falling (↓) against the US dollar. "
                   "Size is the position as a multiple of the account value.\n")
        out.append("| Currency | Bet vs USD | Size |\n|---|---|---:|")
        for ccy, w in h:
            out.append(f"| {ccy} | {'↑ rises' if w > 0 else '↓ falls'} | {abs(w):.2f}× |")
        gross = sum(abs(w) for _, w in h)
        out.append(f"\nTotal exposure: **{gross:.2f}×** the account value.")
    else:
        out.append("Nothing at the moment (all cash).")

    # trades
    out.append("\n## Today's trades\n")
    if not ptr and not qtr:
        out.append("None today." + (f" OANDA practice: {note}." if note else ""))
    else:
        if ptr:
            out.append(f"- **Paper:** {trades_text(ptr)}")
        if qst is not None:
            if qtr and set(qtr) == set(ptr):
                out.append("- **OANDA practice:** the same trades, filled at OANDA ✅")
            elif qtr:
                out.append(f"- **OANDA practice:** {trades_text(qtr)}")
            else:
                out.append(f"- **OANDA practice:** no trades ({note or 'nothing needed'})")

    # chart
    peq, qeq = _csv(root / s["paper"] / "equity.csv"), _csv(root / s["practice"] / "equity.csv")
    series = {}
    if pst:
        series["Paper"] = _pct_series(peq, "equity", pst["start"])
    if qst:
        series["OANDA practice"] = _pct_series(qeq, "nav", qst["start"])
    if any(len(x) for x in series.values()):
        (root / s["paper"] / "report_equity.svg").write_text(
            svg_lines(series, f"{s['name']}: % change since start"))
        out.append("\n## Performance\n\n![Account value over time](report_equity.svg)")

    # learning-model scorecard
    if key == "ml":
        from .ml_paper import live_scorecard
        sc = live_scorecard(root / s["paper"])
        n = sc.get("weeks_scored", 0)
        out.append("\n## Is the model predicting well?\n")
        if n == 0:
            out.append("No full week scored yet. The first prediction is scored after its week ends.")
        else:
            out.append(f"| | Live | Backtest (2015–26) | Useful level |\n|---|---:|---:|---:|\n"
                       f"| Prediction accuracy (IC) | {sc.get('mean_IC', 0):+.3f} | +0.014 | 0.05 or more |\n"
                       f"| Weeks the bought currencies beat the sold ones | "
                       f"{sc.get('weeks_long_beat_short_%')}% | – | well above 50% |\n"
                       f"| Weeks scored | {n} | – | 26 or more |")
            out.append("\nFewer than ~26 scored weeks says very little either way.")
        fi = _csv(root / s["paper"] / "feature_importance.csv")
        if fi is not None and len(fi):
            out.append("\n<details><summary>Inputs the model relied on most</summary>\n\n"
                       + ", ".join(str(x) for x in fi.iloc[:, 0].tolist()) + "\n\n</details>")

    # daily history
    rows = []
    pdays = _pct_series(peq, "equity", pst["start"]) if pst else pd.Series(dtype=float)
    qdays = _pct_series(qeq, "nav", qst["start"]) if qst else pd.Series(dtype=float)
    for d in sorted(set(pdays.index) | set(qdays.index), reverse=True)[:30]:
        pv = f"{_pct(pdays[d])}" if d in pdays.index else "–"
        qv = f"{_pct(qdays[d])}" if d in qdays.index else "–"
        rows.append(f"| {d} | {pv} | {qv} |")
    if rows:
        out.append("\n<details><summary>Daily history (change since start, latest first)</summary>\n\n"
                   "| Date | Paper | OANDA practice |\n|---|---:|---:|\n" + "\n".join(rows) + "\n\n</details>")

    # go-live checklist
    if checks:
        out.append(f"\n## Go-live check: {GATE_WORDS.get(v, v)}\n")
        out.append("| | Check | Detail |\n|---|---|---|")
        for c in checks:
            out.append(f"| {STATUS_ICON.get(c.status, '')} | {GATE_PLAIN.get(c.name, c.name)} | {c.detail} |")
    out.append("\n---\n⚠️ The backtest found **no edge** for this strategy after costs (see "
               "[results/RESEARCH.md](../results/RESEARCH.md)). These accounts are here to check that on live "
               "data. Don't fund it. · [Overview](../REPORT.md)")
    md = "\n".join(out) + "\n"
    (root / s["paper"]).mkdir(parents=True, exist_ok=True)    # a strategy that hasn't started yet
    (root / s["paper"] / "REPORT.md").write_text(md)
    return md


# ---------- overview page ----------------------------------------------------------------------
def overview_page(cfg: dict, root: Path, now: datetime) -> str:
    today = now.strftime("%Y-%m-%d")
    out = ["# FX bot overview", "",
           f"Updated {now:%a %d %b %Y, %H:%M} UTC · **practice and simulated money only, no real trades**",
           "", "| Strategy | Account | Value | Today | Since start |", "|---|---|---:|---|---|"]
    trades = []
    for key, s in STRATEGIES.items():
        pst, ptr = _paper(root, s["paper"], today)
        qst, qtr, note = _practice(root, s["practice"], today)
        link = f"[{s['icon']} {s['name']}]({s['paper']}/REPORT.md)"
        for i, (label, st) in enumerate((("Paper (simulated)", pst), ("OANDA practice", qst))):
            v = f"**{_money(st['value'], st['ccy'])}**" if st else "not started"
            out.append(f"| {link if i == 0 else ''} | {label} | {v} | {_cell_change(st, 'day')} | "
                       f"{_cell_change(st, 'total')} |")
        t = trades_text(ptr) if ptr else "none"
        if qst is not None and ptr:
            t += " · OANDA: " + ("same, filled ✅" if qtr and set(qtr) == set(ptr)
                                 else (trades_text(qtr) if qtr else f"none ({note or 'nothing needed'})"))
        trades.append(f"- **{s['icon']} {s['name']}:** {t}")
    out += ["", "## Today's trades", *trades, "", "## Go-live check",
            "A strategy is only eligible for a small live trial when every check passes "
            "(details on each strategy page).", ""]
    for key, s in STRATEGIES.items():
        checks, v = _gate(cfg, root, key)
        dur = next((c.detail for c in checks if c.name == "duration"), "")
        failing = [GATE_PLAIN.get(c.name, c.name).lower() for c in checks if c.status == "FAIL"]
        out.append(f"- **{s['icon']} {s['name']}:** {GATE_WORDS.get(v, v)}"
                   + (f" ({dur})" if dur else "") + (f" · failing: {', '.join(failing)}" if failing else ""))
    out += ["", "## Coming up",
            "- Every weekday, about 02:17 UTC (GitHub can start scheduled runs late): both strategies run, the daily summary goes to your phone",
            "- 16 Feb 2027: early review (about 13 weeks of data)",
            "- 18 May 2027: decision review (about 26 weeks): the go-live check gives the answer",
            "", "---",
            "Research: [backtest](results/BACKTEST.md) · [other strategies tried](results/RESEARCH.md) · "
            "[learning model](results/MODEL.md) · [go-live criteria](results/GATE.md)"]
    md = "\n".join(out) + "\n"
    (root / "REPORT.md").write_text(md)
    return md


def write_all(cfg: dict, root: Path, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    for key in STRATEGIES:
        strategy_page(cfg, root, key, now)
    return overview_page(cfg, root, now)
