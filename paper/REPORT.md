# 📈 Forex trend strategy

Updated Thu 19 Nov 2026, 10:18 UTC · **practice and simulated money only, no real trades**

> Follows the trend of each of the 7 major currency pairs: 7 fixed signals per pair (price vs its 20/50/100/200-day averages, 30/90/180-day momentum). Long when the trend is up, short when it's down, sized to a 10% volatility target. Trades when a pair's signal changes.

## At a glance

| | Paper (simulated $) | OANDA practice (demo £) |
|---|---:|---:|
| **Account value** | **$10,123.11** | **£100,851.01** |
| Today | 🔴 −$11.42 (−0.11%) | 🔴 −£109.01 (−0.11%) |
| Since start | 🟢 +1.23% (since 2026-11-14) | 🟢 +0.85% (since 2026-11-14) |
| Trading costs paid | $5.80 | in the OANDA fill prices |
| Go-live check | ⛔ not ready (0.6 of 26 weeks) | |

## What it's betting on

Each position is a bet on a currency rising (↑) or falling (↓) against the US dollar. Size is the position as a multiple of the account value.

| Currency | Bet vs USD | Size |
|---|---|---:|
| EUR | ↓ falls | 0.71× |
| GBP | ↓ falls | 0.32× |
| JPY | ↓ falls | 0.33× |
| AUD | ↓ falls | 0.49× |
| CAD | ↓ falls | 0.74× |
| CHF | ↓ falls | 0.51× |
| NZD | ↓ falls | 0.47× |

Total exposure: **3.57×** the account value.

## Today's trades

- **Paper:** bought GBP/USD
- **OANDA practice:** the same trades, filled at OANDA ✅

## Performance

![Account value over time](report_equity.svg)

<details><summary>Daily history (change since start, latest first)</summary>

| Date | Paper | OANDA practice |
|---|---:|---:|
| 2026-11-19 | +1.23% | +0.85% |
| 2026-11-18 | +1.35% | +0.96% |
| 2026-11-17 | +0.85% | +0.16% |
| 2026-11-16 | – | −0.03% |
| 2026-11-14 | −0.05% | +0.00% |

</details>

## Go-live check: ⛔ not ready

| | Check | Detail |
|---|---|---|
| ⏳ | Long enough on OANDA practice | 0.6 of 26 weeks |
| ⏳ | Making money after costs | practice return +0.85% after all costs |
| ⏳ | Real costs close to the assumptions | fills 0.70 bps vs assumed 1.32 bps (max x1.25); financing: too early to judge (4 of 10 weekdays held) |
| ✅ | Practice matches paper | practice +0.85% vs paper +1.28% (gap -0.43 pts, max 3) |
| ❌ | Runs reliably (no misses, mismatches, halts) | missed weekdays 0; mismatches 1; order problems 2; not halted |
| ✅ | Losses stay limited | worst fall -0.3% (limit -20%) |

---
⚠️ The backtest found **no edge** for this strategy after costs (see [results/RESEARCH.md](../results/RESEARCH.md)). These accounts are here to check that on live data. Don't fund it. · [Overview](../REPORT.md)
