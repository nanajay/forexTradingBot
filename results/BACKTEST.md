# Forex backtest: trend "blend" strategy on the 7 major currency pairs

`python -m fxbot backtest`. Daily Yahoo Finance closes for EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF, NZD/USD, 2004-01-01 to 2026-11-13
(one-day bad ticks that revert the next day are removed). The position decided at day t's close earns day t+1's
return. Each trade pays half the pair's spread (EUR/USD 1.0, GBP/USD 1.5, USD/JPY 1.2, AUD/USD 1.5, USD/CAD 2.0, USD/CHF 2.0, NZD/USD 2.5 bps)
+ 0.5 bp slippage. Open positions pay 50 bp/yr financing on gross notional.
No-trade band 15% of the signal range. Each pair targets
10%/sqrt(N) volatility, fixed when its signal changes
(caps: 2.0x per pair, 4.0x gross).
The forex trend rules use fixed parameters (20/50/100/200-day SMA, 30/90/180-day momentum), first used in the TradingBot crypto project, and were **not tuned** on forex data.

## Verdict

The strategy does **not** carry over to FX in its configured `long_short` mode: it lost money from 2015 to 2026 **even with zero costs** (-4.7% a year), so the signal itself stopped working and cheaper execution won't fix it. After costs: -6.7% a year. Check the single-rule grid below before blaming one parameter. Paper-trade it to watch it live. Don't fund it.

## Results

| Mode | Costs | Period | CAGR | Max DD | Sharpe | Vol | Worst year | Costs/yr |
|---|---|---|---:|---:|---:|---:|---:|---:|
| long_short | after costs | full | -1.5% | -61.0% | -0.03 | 14.6% | -17.2% | 1.88% |
| long_short | after costs | first half | +4.4% | -29.4% | 0.37 | 14.1% | -11.9% | 1.57% |
| long_short | after costs | second half | -6.7% | -61.0% | -0.38 | 15.1% | -17.2% | 2.16% |
| long_short | no costs | full | +0.4% | -51.0% | 0.10 | 14.6% | -15.1% | 0.00% |
| long_short | no costs | first half | +6.0% | -26.8% | 0.49 | 14.1% | -10.6% | 0.00% |
| long_short | no costs | second half | -4.7% | -51.0% | -0.24 | 15.1% | -15.1% | 0.00% |
| long_only | after costs | full | -1.2% | -39.8% | -0.11 | 8.0% | -11.2% | 1.14% |
| long_only | after costs | first half | +2.2% | -20.0% | 0.31 | 8.1% | -6.9% | 0.99% |
| long_only | after costs | second half | -4.3% | -39.8% | -0.51 | 8.0% | -11.2% | 1.28% |
| long_only | no costs | full | -0.1% | -32.2% | 0.03 | 8.0% | -10.0% | 0.00% |
| long_only | no costs | first half | +3.2% | -17.9% | 0.43 | 8.1% | -6.2% | 0.00% |
| long_only | no costs | second half | -3.1% | -32.2% | -0.35 | 8.0% | -10.0% | 0.00% |

`long_short`: each rule votes +1/-1, so the bot can be short a pair (natural for FX). `long_only`: each rule votes
1/0, so a pair is held long or flat (the original long-only design).

## Robustness: single rules (long_short, after costs)

| Rule | CAGR 2004-2014 | Sharpe | CAGR 2015-2026 | Sharpe |
|---|---:|---:|---:|---:|
| blend (7 rules) | +4.4% | 0.37 | -6.7% | -0.38 |
| sma_20 | -7.2% | -0.41 | -8.6% | -0.46 |
| sma_50 | -0.9% | 0.03 | -10.8% | -0.56 |
| sma_100 | +2.6% | 0.23 | -9.3% | -0.44 |
| sma_200 | +3.8% | 0.31 | -10.4% | -0.48 |
| mom_30 | -2.1% | -0.05 | -5.6% | -0.26 |
| mom_90 | +7.3% | 0.48 | -13.2% | -0.64 |
| mom_180 | -1.7% | -0.00 | -8.0% | -0.32 |

## Per pair (blend, long_short, after costs, each pair traded alone)

| Pair | CAGR 2004-2014 | Sharpe | CAGR 2015-2026 | Sharpe |
|---|---:|---:|---:|---:|
| EUR/USD | +2.4% | 0.33 | +0.6% | 0.11 |
| GBP/USD | +0.8% | 0.14 | -3.0% | -0.30 |
| USD/JPY | +1.8% | 0.24 | -0.5% | -0.01 |
| AUD/USD | +4.3% | 0.48 | -2.8% | -0.28 |
| USD/CAD | +0.2% | 0.07 | -3.0% | -0.32 |
| USD/CHF | +0.8% | 0.13 | -6.0% | -0.56 |
| NZD/USD | +0.5% | 0.10 | -3.3% | -0.36 |

## Caveats
* Yahoo's daily FX closes are composite quotes, not a broker's prices. Spreads and financing are flat
  assumptions; real swap rates vary by pair, direction and interest-rate regime (positive carry is ignored).
* Weights are treated as a constant fraction of equity between signal changes (a standard backtest
  approximation).
* Past performance does not guarantee future results.
