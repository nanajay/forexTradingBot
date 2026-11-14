"""Readable reports: paper/REPORT.md (+ equity SVG) and results/BACKTEST.md."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import strategy as S
from .paper import State


def svg_line(series: pd.Series, title: str, width: int = 720, height: int = 260) -> str:
    """Tiny dependency-free SVG line chart of a % series."""
    pad_l, pad_r, pad_t, pad_b = 56, 16, 28, 32
    y = series.astype(float).to_numpy()
    lo, hi = min(y.min(), 0.0), max(y.max(), 0.0)
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    n = len(y)
    def X(i): return pad_l + (width - pad_l - pad_r) * (i / max(n - 1, 1))
    def Y(v): return pad_t + (height - pad_t - pad_b) * (1 - (v - lo) / (hi - lo))
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(y))
    ticks = "".join(
        f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#ccc" stroke-width="0.5"/>'
        f'<text x="{pad_l - 6}" y="{Y(v) + 4:.1f}" font-size="11" text-anchor="end" fill="#666">{v:+.1f}%</text>'
        for v in [lo, (lo + hi) / 2, hi])
    labels = (f'<text x="{pad_l}" y="{height - 10}" font-size="11" fill="#666">{series.index[0]}</text>'
              f'<text x="{width - pad_r}" y="{height - 10}" font-size="11" text-anchor="end" fill="#666">'
              f'{series.index[-1]}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#fff"/>'
            f'<text x="{pad_l}" y="18" font-size="13" fill="#222">{title}</text>{ticks}'
            f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="#888"/>'
            f'<polyline fill="none" stroke="#2563eb" stroke-width="2" points="{pts}"/>{labels}</svg>')


def paper_report(cfg: dict, state_dir: Path) -> str:
    st = State.load(state_dir)
    if not st or not (state_dir / "equity.csv").exists():
        return "No paper account yet."
    eq = pd.read_csv(state_dir / "equity.csv")
    last = eq.iloc[-1]
    chg = (st.balance / st.initial_capital - 1) * 100
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mode = cfg["strategy"]["mode"].replace("_", "/")
    rows = []
    for p in cfg["pairs"]:
        k = p.replace("/", "")
        u = st.units.get(p, 0.0)
        side = "long" if u > 0 else "short" if u < 0 else "flat"
        rows.append(f"| {p} | {last[f'{k}_px']:.5g} | {st.signal.get(p, 0):+.2f} | {side} | "
                    f"{last[f'{k}_w']:+.2f}x |")
    pct = (eq.set_index("signal_day")["equity"] / st.initial_capital - 1) * 100
    (state_dir / "report_equity.svg").write_text(svg_line(pct, "Paper account, % change since start"))
    table = "\n".join(f"| {d} | ${e:,.2f} | {v:+.2f}% |"
                      for d, e, v in zip(eq.signal_day, eq.equity, pct))
    md = f"""# Forex trend bot: paper report

Updated {now} · signal day {last.signal_day} · **simulated: no real money**

**Strategy:** the TradingBot BTC/ETH trend rules applied to {len(cfg['pairs'])} major USD pairs: 7 fixed
signals per pair (price vs its 20/50/100/200-day averages, 30/90/180-day momentum), {mode},
{cfg['strategy']['band']:.0%} no-trade band, positions sized to a {cfg['sizing']['vol_target']:.0%} volatility target.
No learning model.

> **Backtest warning:** after costs this strategy lost money on FX from 2015 to 2026 (see
> [results/BACKTEST.md](../results/BACKTEST.md)). This paper account tracks it live; it is not a
> recommendation to trade it.

| | |
|---|---|
| Account value | **${st.balance:,.2f}** |
| Change since start ({st.started[:10]}) | {chg:+.2f}% |
| Gross leverage | {last.gross_leverage:.2f}x |
| Trading costs paid | ${st.costs_paid:,.2f} |
| Financing paid | ${st.financing_paid:,.2f} |

## Positions

| Pair | Price | Signal (-1..+1) | Side | Size (x equity) |
|---|---:|---:|---|---:|
{chr(10).join(rows)}

## Account

![Paper account, % change since start](report_equity.svg)

| Signal day | Equity | Change |
|---|---:|---:|
{table}
"""
    (state_dir / "REPORT.md").write_text(md)
    return md


def _fmt(p: dict) -> str:
    return (f"{p['CAGR_%']:+.1f}% | {p['maxDD_%']:.1f}% | {p['sharpe']:.2f} | {p['vol_%']:.1f}% | "
            f"{p['worst_year_%']:+.1f}%")


def backtest_report(closes: pd.DataFrame, cfg: dict, out_dir: Path) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    start, split = cfg["backtest"]["start"], cfg["backtest"]["split"]
    first_half_end = str((pd.Timestamp(split) - pd.Timedelta(days=1)).date())
    periods = [("full", start, None), ("first half", start, first_half_end), ("second half", split, None)]
    end = str(closes.index[-1].date())

    def variant(**kw):
        k = copy.deepcopy(cfg)
        for sect, vals in kw.items():
            k[sect].update(vals)
        return k

    def zero_cost(k):
        k = copy.deepcopy(k)
        k["costs"] = {"slippage_bps": 0.0, "financing_bps_year": 0.0}
        k["pairs"] = {p: [v[0], 0.0] for p, v in k["pairs"].items()}
        return k

    lines, curves, second = [], {}, {}
    for mode in ("long_short", "long_only"):
        k = variant(strategy={"mode": mode})
        for label, kk in (("after costs", k), ("no costs", zero_cost(k))):
            for pname, s, e in periods:
                res, p, _ = S.run(closes, kk, s, e)
                lines.append(f"| {mode} | {label} | {pname} | {_fmt(p)} | {p['costs_%_yr']:.2f}% |")
                if pname == "second half":
                    second[(mode, label)] = p["CAGR_%"]
                if pname == "full":
                    curves[f"{mode} {label}"] = (1 + res["ret"]).cumprod()
    pd.DataFrame(curves).to_csv(out_dir / "equity_curves.csv", float_format="%.5f")

    grid = []
    rules = [("blend (7 rules)", cfg["strategy"]["sma"], cfg["strategy"]["mom"])]
    rules += [(f"sma_{n}", [n], []) for n in cfg["strategy"]["sma"]]
    rules += [(f"mom_{n}", [], [n]) for n in cfg["strategy"]["mom"]]
    for name, sma, mom in rules:
        k = variant(strategy={"sma": sma, "mom": mom})
        cells = []
        for _, s, e in periods[1:]:
            _, p, _ = S.run(closes, k, s, e)
            cells.append(f"{p['CAGR_%']:+.1f}% | {p['sharpe']:.2f}")
        grid.append(f"| {name} | {' | '.join(cells)} |")

    per_pair = []
    for pair in cfg["pairs"]:
        k = copy.deepcopy(cfg)
        k["pairs"] = {pair: cfg["pairs"][pair]}
        cells = []
        for _, s, e in periods[1:]:
            _, p, _ = S.run(closes[[pair]], k, s, e)
            cells.append(f"{p['CAGR_%']:+.1f}% | {p['sharpe']:.2f}")
        per_pair.append(f"| {pair} | {' | '.join(cells)} |")

    mode = cfg["strategy"]["mode"]
    if second[(mode, "no costs")] < 0:
        verdict = (f"The strategy does **not** carry over to FX in its configured `{mode}` mode: it lost money from "
                   f"{split[:4]} to {end[:4]} **even with zero costs** ({second[(mode, 'no costs')]:+.1f}% a year), so "
                   f"the signal itself stopped working and cheaper execution won't fix it. After costs: "
                   f"{second[(mode, 'after costs')]:+.1f}% a year. Check the single-rule grid below before blaming one "
                   f"parameter. Paper-trade it to watch it live. Don't fund it.")
    elif second[(mode, "after costs")] < 0:
        verdict = (f"The signal still has an edge before costs from {split[:4]} to {end[:4]} "
                   f"({second[(mode, 'no costs')]:+.1f}% a year), but costs turn it into a loss "
                   f"({second[(mode, 'after costs')]:+.1f}% a year). Don't fund it as configured.")
    else:
        verdict = (f"Profitable after costs from {split[:4]} to {end[:4]} ({second[(mode, 'after costs')]:+.1f}% a "
                   f"year). Check the drawdowns and the robustness grid before trusting it.")
    c = cfg["costs"]
    md = f"""# Forex backtest: TradingBot trend "blend" on FX majors

`python -m fxbot backtest`. Daily Yahoo Finance closes for {', '.join(cfg['pairs'])}, {start} to {end}
(one-day bad ticks that revert the next day are removed). The position decided at day t's close earns day t+1's
return. Each trade pays half the pair's spread ({', '.join(f'{p} {v[1]}' for p, v in cfg['pairs'].items())} bps)
+ {c['slippage_bps']} bp slippage. Open positions pay {c['financing_bps_year']} bp/yr financing on gross notional.
No-trade band {cfg['strategy']['band']:.0%} of the signal range. Each pair targets
{cfg['sizing']['vol_target']:.0%}/sqrt(N) volatility, fixed when its signal changes
(caps: {cfg['sizing']['max_pair_leverage']}x per pair, {cfg['sizing']['max_gross_leverage']}x gross).
The rule parameters are the crypto bot's (20/50/100/200-day SMA, 30/90/180-day momentum) and were **not tuned** on FX.

## Verdict

{verdict}

## Results

| Mode | Costs | Period | CAGR | Max DD | Sharpe | Vol | Worst year | Costs/yr |
|---|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

`long_short`: each rule votes +1/-1, so the bot can be short a pair (natural for FX). `long_only`: each rule votes
1/0 exactly like the crypto bot, so a pair is held long or flat.

## Robustness: single rules (long_short, after costs)

| Rule | CAGR {start[:4]}-{first_half_end[:4]} | Sharpe | CAGR {split[:4]}-{end[:4]} | Sharpe |
|---|---:|---:|---:|---:|
{chr(10).join(grid)}

## Per pair (blend, long_short, after costs, each pair traded alone)

| Pair | CAGR {start[:4]}-{first_half_end[:4]} | Sharpe | CAGR {split[:4]}-{end[:4]} | Sharpe |
|---|---:|---:|---:|---:|
{chr(10).join(per_pair)}

## Caveats
* Yahoo's daily FX closes are composite quotes, not a broker's prices. Spreads and financing are flat
  assumptions; real swap rates vary by pair, direction and interest-rate regime (positive carry is ignored).
* Weights are treated as a constant fraction of equity between signal changes (same approximation as the crypto
  backtest).
* Past performance does not guarantee future results.
"""
    (out_dir / "BACKTEST.md").write_text(md)
    return md
