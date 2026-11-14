# Forex trend bot: paper report

Updated 2026-11-14 15:50 UTC · signal day 2026-11-13 · **simulated: no real money**

**Strategy:** the TradingBot BTC/ETH trend rules applied to 7 major USD pairs: 7 fixed
signals per pair (price vs its 20/50/100/200-day averages, 30/90/180-day momentum), long/short,
15% no-trade band, positions sized to a 10% volatility target.
No learning model.

> **Backtest warning:** after costs this strategy lost money on FX from 2015 to 2026 (see
> [results/BACKTEST.md](../results/BACKTEST.md)). This paper account tracks it live; it is not a
> recommendation to trade it.

| | |
|---|---|
| Account value | **$9,994.68** |
| Change since start (2026-11-14) | -0.05% |
| Gross leverage | 4.00x |
| Trading costs paid | $5.32 |
| Financing paid | $0.00 |

## Positions

| Pair | Price | Signal (-1..+1) | Side | Size (x equity) |
|---|---:|---:|---|---:|
| EUR/USD | 1.1028 | -1.00 | short | -0.72x |
| GBP/USD | 1.3209 | -1.00 | short | -0.70x |
| USD/JPY | 159.69 | +0.71 | long | +0.34x |
| AUD/USD | 0.6774 | -1.00 | short | -0.50x |
| USD/CAD | 1.4269 | +1.00 | long | +0.75x |
| USD/CHF | 0.8382 | +1.00 | long | +0.51x |
| NZD/USD | 0.5525 | -1.00 | short | -0.47x |

## Account

![Paper account, % change since start](report_equity.svg)

| Signal day | Equity | Change |
|---|---:|---:|
| 2026-11-13 | $9,994.68 | -0.05% |
