# FX bot overview

Updated Mon 23 Nov 2026, 10:45 UTC · **practice and simulated money only, no real trades**

| Strategy | Account | Value | Today | Since start |
|---|---|---:|---|---|
| [📈 Forex trend strategy](paper/REPORT.md) | Paper (simulated) | **$10,228.39** | 🟢 +$32.49 (+0.32%) | 🟢 +2.28% |
|  | OANDA practice | **£101,958.66** | 🟢 +£359.05 (+0.35%) | 🟢 +1.96% |
| [🤖 Forex learning model](paper_ml/REPORT.md) | Paper (simulated) | **$10,106.46** | 🔴 −$52.50 (−0.52%) | 🟢 +1.06% |
|  | OANDA practice | **£100,830.45** | 🔴 −£502.51 (−0.50%) | 🟢 +0.83% |

## Today's trades
- **📈 Forex trend strategy:** none
- **🤖 Forex learning model:** bought AUD/USD, NZD/USD, USD/CHF, USD/JPY · sold EUR/USD, GBP/USD, USD/CAD · OANDA: bought AUD/USD, USD/CHF, USD/JPY · sold EUR/USD, USD/CAD

## Go-live check
A strategy is only eligible for a small live trial when every check passes (details on each strategy page).

- **📈 Forex trend strategy:** ⛔ not ready (1.1 of 26 weeks) · failing: runs reliably (no misses, mismatches, halts)
- **🤖 Forex learning model:** ⏳ waiting for data (1.1 of 26 weeks)

## Coming up
- Every weekday, about 02:17 UTC (GitHub can start scheduled runs late): both strategies run, the daily summary goes to your phone
- 16 Feb 2027: early review (about 13 weeks of data)
- 18 May 2027: decision review (about 26 weeks): the go-live check gives the answer

---
Research: [backtest](results/BACKTEST.md) · [other strategies tried](results/RESEARCH.md) · [learning model](results/MODEL.md) · [go-live criteria](results/GATE.md)
