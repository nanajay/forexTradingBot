# 🤖 Forex learning model

Updated Sat 14 Nov 2026, 17:34 UTC · **practice and simulated money only, no real trades**

> A LightGBM model retrained every week on 24 inputs per currency (momentum, trend, volatility, interest rates, market mood). Each Monday it buys the 3 currencies it expects to be strongest next week and sells the 3 weakest, with no net bet on the dollar, 10% volatility target.

## At a glance

| | Paper (simulated $) | OANDA practice (demo £) |
|---|---:|---:|
| **Account value** | **$9,994.68** | **£100,000.00** |
| Today | ⚪ first day | ⚪ first day |
| Since start | 🔴 −0.05% (since 2026-11-14) | ⚪ +0.00% (since 2026-11-14) |
| Trading costs paid | $5.23 | in the OANDA fill prices |
| Go-live check | ⏳ waiting for data (0.0 of 26 weeks) | |

## What it's betting on

Each position is a bet on a currency rising (↑) or falling (↓) against the US dollar. Size is the position as a multiple of the account value.

| Currency | Bet vs USD | Size |
|---|---|---:|
| EUR | ↑ rises | 0.67× |
| GBP | ↓ falls | 0.67× |
| JPY | ↑ rises | 0.67× |
| AUD | ↓ falls | 0.67× |
| CAD | ↓ falls | 0.67× |
| NZD | ↑ rises | 0.67× |

Total exposure: **4.00×** the account value.

## Today's trades

- **Paper:** bought EUR/USD, NZD/USD, USD/CAD · sold AUD/USD, GBP/USD, USD/JPY
- **OANDA practice:** no trades (market closed)

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
| 2026-11-14 | −0.05% | +0.00% |

</details>

## Go-live check: ⏳ waiting for data

| | Check | Detail |
|---|---|---|
| ⏳ | Long enough on OANDA practice | 0.0 of 26 weeks |
| ⏳ | Making money after costs | practice return +0.00% after all costs; live IC: 0 week(s) scored |
| ⏳ | Real costs close to the assumptions | no filled practice orders yet |
| ✅ | Practice matches paper | practice +0.00% vs paper -0.00% (gap +0.00 pts, max 3) |
| ✅ | Runs reliably (no misses, mismatches, halts) | missed weekdays 0; mismatches 0; order problems 0; not halted |
| ✅ | Losses stay limited | worst fall 0.0% (limit -20%) |

---
⚠️ The backtest found **no edge** for this strategy after costs (see [results/RESEARCH.md](../results/RESEARCH.md)). These accounts are here to check that on live data. Don't fund it. · [Overview](../REPORT.md)
