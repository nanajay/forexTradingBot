"""results/BACKTEST.md (the report pages are built by fxbot/pages.py)."""
from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

from . import strategy as S


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
    md = f"""# Forex backtest: trend "blend" strategy on the 7 major currency pairs

`python -m fxbot backtest`. Daily Yahoo Finance closes for {', '.join(cfg['pairs'])}, {start} to {end}
(one-day bad ticks that revert the next day are removed). The position decided at day t's close earns day t+1's
return. Each trade pays half the pair's spread ({', '.join(f'{p} {v[1]}' for p, v in cfg['pairs'].items())} bps)
+ {c['slippage_bps']} bp slippage. Open positions pay {c['financing_bps_year']} bp/yr financing on gross notional.
No-trade band {cfg['strategy']['band']:.0%} of the signal range. Each pair targets
{cfg['sizing']['vol_target']:.0%}/sqrt(N) volatility, fixed when its signal changes
(caps: {cfg['sizing']['max_pair_leverage']}x per pair, {cfg['sizing']['max_gross_leverage']}x gross).
The forex trend rules use fixed parameters (20/50/100/200-day SMA, 30/90/180-day momentum), first used in the TradingBot crypto project, and were **not tuned** on forex data.

## Verdict

{verdict}

## Results

| Mode | Costs | Period | CAGR | Max DD | Sharpe | Vol | Worst year | Costs/yr |
|---|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

`long_short`: each rule votes +1/-1, so the bot can be short a pair (natural for FX). `long_only`: each rule votes
1/0, so a pair is held long or flat (the original long-only design).

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
* Weights are treated as a constant fraction of equity between signal changes (a standard backtest
  approximation).
* Past performance does not guarantee future results.
"""
    (out_dir / "BACKTEST.md").write_text(md)
    return md
