# 🤖 Forex learning model

Updated Fri 20 Nov 2026, 09:59 UTC · **practice and simulated money only, no real trades**

> A LightGBM model retrained every week on 24 inputs per currency (momentum, trend, volatility, interest rates, market mood). Each Monday it buys the 3 currencies it expects to be strongest next week and sells the 3 weakest, with no net bet on the dollar, 10% volatility target.

## At a glance

| | Paper (simulated $) | OANDA practice (demo £) |
|---|---:|---:|
| **Account value** | **$10,158.96** | **£101,332.96** |
| Today | 🟢 +$84.95 (+0.84%) | 🟢 +£837.86 (+0.83%) |
| Since start | 🟢 +1.59% (since 2026-11-14) | 🟢 +1.33% (since 2026-11-14) |
| Trading costs paid | $5.23 | in the OANDA fill prices |
| Go-live check | ⏳ waiting for data (0.7 of 26 weeks) | |

## What it's betting on

Each position is a bet on a currency rising (↑) or falling (↓) against the US dollar. Size is the position as a multiple of the account value.

| Currency | Bet vs USD | Size |
|---|---|---:|
| EUR | ↑ rises | 0.65× |
| GBP | ↓ falls | 0.65× |
| JPY | ↑ rises | 0.66× |
| AUD | ↓ falls | 0.65× |
| CAD | ↓ falls | 0.66× |
| NZD | ↑ rises | 0.65× |

Total exposure: **3.92×** the account value.

## Today's trades

None today.

## Performance

![Account value over time](report_equity.svg)

## Is the model predicting well?

No full week scored yet. The first prediction is scored after its week ends.

<details><summary>Inputs the model relied on most</summary>

carry, vol_ratio, vol_level, mom_5, carry_x_vixchg, dist_sma50, rsi14, mom_20, dist_sma200, mom_250

</details>

<details><summary>Daily history (change since start, latest first)</summary>

| Date | Paper | OANDA practice |
|---|---:|---:|
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
| ⏳ | Long enough on OANDA practice | 0.7 of 26 weeks |
| ⏳ | Making money after costs | practice return +1.33% after all costs; live IC: 0 week(s) scored |
| ⏳ | Real costs close to the assumptions | fills 0.67 bps vs assumed 1.31 bps (max x1.25); financing: too early to judge (5 of 10 weekdays held) |
| ✅ | Practice matches paper | practice +1.33% vs paper +1.64% (gap -0.31 pts, max 3) |
| ✅ | Runs reliably (no misses, mismatches, halts) | missed weekdays 0; mismatches 0; order problems 0; not halted |
| ✅ | Losses stay limited | worst fall -0.1% (limit -20%) |

---
⚠️ The backtest found **no edge** for this strategy after costs (see [results/RESEARCH.md](../results/RESEARCH.md)). These accounts are here to check that on live data. Don't fund it. · [Overview](../REPORT.md)
