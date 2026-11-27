# 📈 Forex trend strategy

Updated Fri 27 Nov 2026, 10:50 UTC · **practice and simulated money only, no real trades**

> Follows the trend of each of the 7 major currency pairs: 7 fixed signals per pair (price vs its 20/50/100/200-day averages, 30/90/180-day momentum). Long when the trend is up, short when it's down, sized to a 10% volatility target. Trades when a pair's signal changes.

## At a glance

| | Paper (simulated $) | OANDA practice (demo £) |
|---|---:|---:|
| **Account value** | **$10,127.88** | **£100,960.39** |
| Today | 🔴 −$11.71 (−0.12%) | 🔴 −£129.24 (−0.13%) |
| Since start | 🟢 +1.28% (since 2026-11-14) | 🟢 +0.96% (since 2026-11-14) |
| Trading costs paid | $6.33 | in the OANDA fill prices |
| Go-live check | ⛔ not ready (1.7 of 26 weeks) | |

## What it's betting on

Each position is a bet on a currency rising (↑) or falling (↓) against the US dollar. Size is the position as a multiple of the account value.

| Currency | Bet vs USD | Size |
|---|---|---:|
| EUR | ↓ falls | 0.71× |
| GBP | ↓ falls | 0.74× |
| JPY | ↓ falls | 0.33× |
| AUD | ↓ falls | 0.49× |
| CAD | ↓ falls | 0.74× |
| CHF | ↓ falls | 0.51× |
| NZD | ↓ falls | 0.46× |

Total exposure: **3.98×** the account value.

## Today's trades

None today.

## Performance

![Account value over time](report_equity.svg)

<details><summary>Daily history (change since start, latest first)</summary>

| Date | Paper | OANDA practice |
|---|---:|---:|
| 2026-11-27 | +1.28% | +0.96% |
| 2026-11-26 | +1.40% | +1.09% |
| 2026-11-25 | +2.67% | +2.33% |
| 2026-11-24 | +2.41% | +2.08% |
| 2026-11-23 | +2.28% | +1.96% |
| 2026-11-20 | +1.96% | +1.60% |
| 2026-11-19 | +1.23% | +0.85% |
| 2026-11-18 | +1.35% | +0.96% |
| 2026-11-17 | +0.85% | +0.16% |
| 2026-11-16 | – | −0.03% |
| 2026-11-14 | −0.05% | +0.00% |

</details>

## Go-live check: ⛔ not ready

| | Check | Detail |
|---|---|---|
| ⏳ | Long enough on OANDA practice | 1.7 of 26 weeks |
| ⏳ | Making money after costs | practice return +0.96% after all costs |
| ✅ | Real costs close to the assumptions | fills 0.68 bps vs assumed 1.32 bps (max x1.25); financing paid -46.62 vs expected 76.67 (paper account doesn't model carry) over 10 weekdays (9 fills) |
| ✅ | Practice matches paper | practice +0.96% vs paper +1.33% (gap -0.37 pts, max 3) |
| ❌ | Runs reliably (no misses, mismatches, halts) | missed weekdays 0; mismatches 1; order problems 2; not halted |
| ✅ | Losses stay limited | worst fall -1.3% (limit -20%) |

---
⚠️ The backtest found **no edge** for this strategy after costs (see [results/RESEARCH.md](../results/RESEARCH.md)). These accounts are here to check that on live data. Don't fund it. · [Overview](../REPORT.md)
