# 🤖 Forex learning model

Updated Mon 23 Nov 2026, 10:45 UTC · **practice and simulated money only, no real trades**

> A LightGBM model retrained every week on 24 inputs per currency (momentum, trend, volatility, interest rates, market mood). Each Monday it buys the 3 currencies it expects to be strongest next week and sells the 3 weakest, with no net bet on the dollar, 10% volatility target.

## At a glance

| | Paper (simulated $) | OANDA practice (demo £) |
|---|---:|---:|
| **Account value** | **$10,106.46** | **£100,830.45** |
| Today | 🔴 −$52.50 (−0.52%) | 🔴 −£502.51 (−0.50%) |
| Since start | 🟢 +1.06% (since 2026-11-14) | 🟢 +0.83% (since 2026-11-14) |
| Trading costs paid | $12.10 | in the OANDA fill prices |
| Go-live check | ⏳ waiting for data (1.1 of 26 weeks) | |

## What it's betting on

Each position is a bet on a currency rising (↑) or falling (↓) against the US dollar. Size is the position as a multiple of the account value.

| Currency | Bet vs USD | Size |
|---|---|---:|
| GBP | ↓ falls | 0.67× |
| JPY | ↓ falls | 0.67× |
| AUD | ↑ rises | 0.67× |
| CAD | ↑ rises | 0.67× |
| CHF | ↓ falls | 0.67× |
| NZD | ↑ rises | 0.67× |

Total exposure: **4.00×** the account value.

## Today's trades

- **Paper:** bought AUD/USD, NZD/USD, USD/CHF, USD/JPY · sold EUR/USD, GBP/USD, USD/CAD
- **OANDA practice:** bought AUD/USD, USD/CHF, USD/JPY · sold EUR/USD, USD/CAD

## Performance

![Account value over time](report_equity.svg)

## Is the model predicting well?

| | Live | Backtest (2015–26) | Useful level |
|---|---:|---:|---:|
| Prediction accuracy (IC) | +0.286 | +0.014 | 0.05 or more |
| Weeks the bought currencies beat the sold ones | 100.0% | – | well above 50% |
| Weeks scored | 1 | – | 26 or more |

Fewer than ~26 scored weeks says very little either way.

<details><summary>Inputs the model relied on most</summary>

carry, vol_ratio, vol_level, mom_5, dist_sma50, rsi14, carry_x_vixchg, dist_sma200, mom_20, mom_250

</details>

<details><summary>Daily history (change since start, latest first)</summary>

| Date | Paper | OANDA practice |
|---|---:|---:|
| 2026-11-23 | +1.06% | +0.83% |
| 2026-11-20 | +1.59% | +1.33% |
| 2026-11-19 | +0.74% | +0.50% |
| 2026-11-18 | +0.24% | +0.06% |
| 2026-11-17 | +0.06% | −0.13% |
| 2026-11-16 | +0.09% | −0.06% |
| 2026-11-14 | −0.05% | +0.00% |

</details>

## Go-live check: ⏳ waiting for data

| | Check | Detail |
|---|---|---|
| ⏳ | Long enough on OANDA practice | 1.1 of 26 weeks |
| ⏳ | Making money after costs | practice return +0.83% after all costs; live IC: 1 week(s) scored |
| ⏳ | Real costs close to the assumptions | fills 0.68 bps vs assumed 1.29 bps (max x1.25); financing: too early to judge (6 of 10 weekdays held) |
| ✅ | Practice matches paper | practice +0.83% vs paper +1.12% (gap -0.29 pts, max 3) |
| ✅ | Runs reliably (no misses, mismatches, halts) | missed weekdays 0; mismatches 0; order problems 0; not halted |
| ✅ | Losses stay limited | worst fall -0.5% (limit -20%) |

---
⚠️ The backtest found **no edge** for this strategy after costs (see [results/RESEARCH.md](../results/RESEARCH.md)). These accounts are here to check that on live data. Don't fund it. · [Overview](../REPORT.md)
