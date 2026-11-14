# Forex Trend Bot

A port of the [TradingBot](https://github.com/nanajay/TradingBot) BTC/ETH trend strategy to the seven major
USD currency pairs, with a daily **paper-trading** account run by GitHub Actions. Simulated money only: there is
no broker connection in this repo.

> **Read this first: the strategy has not worked on FX since 2015.** Backtested on daily closes from 2004 to
> 2026, it made about +4% a year from 2004 to 2014 and lost about −7% a year from 2015 to 2026 after costs
> (−5% a year **before** costs). Every single rule loses over 2015–2026, so this isn't one unlucky parameter.
> Full numbers are in [results/BACKTEST.md](results/BACKTEST.md). Carry, momentum, value and mixes were also
> tested ([results/RESEARCH.md](results/RESEARCH.md)): none made money out of sample. The paper account is here to watch it live,
> not as a reason to fund it.

## The strategy (same rules as the crypto bot)
* **Signals:** on each pair's daily close, 7 fixed on/off rules: price above its 20/50/100/200-day simple
  moving average, and 30/90/180-day return above zero. The **blend** is their average.
* **Direction:** `long_short` (default): each rule votes +1 or −1, so the blend runs from −1 (fully short) to +1
  (fully long), since currencies trend both ways. `long_only` reproduces the crypto bot exactly: votes of 1/0,
  long or flat.
* **No-trade band:** 15% of the signal range, as in the crypto bot. Moves to full long or short, to flat, or
  across zero always go through.
* **Timing:** decided on day t's close, traded straight away, earns day t+1's move. No lookahead (tested).

## What had to change for FX
| | Crypto bot | Forex bot |
|---|---|---|
| Markets | BTC, ETH (50/50) | EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF, NZD/USD |
| Sizing | fixed 50% per coin, no leverage | volatility target: 10%/√7 a year per pair, max 2× per pair, 4× gross |
| Shorting | no (cash when down) | yes, in `long_short` mode |
| Days | 365 calendar days | 252 trading days (Mon–Fri) |
| Costs | 0.40% taker fee + 0.05% slippage | half the spread (1–2.5 bp) + 0.5 bp slippage, plus 0.5%/yr financing |
| Data | Kraken public API | Yahoo Finance public chart API (no key), bad ticks filtered |
| Paper fills | walks Kraken's live order book | latest quote + cost model (no free FX order book) |

Volatility sizing is needed because a currency pair moves roughly a tenth as much as BTC. Without it, results
would be near zero either way. Each pair's size is set when its signal changes and then held, so it doesn't
churn daily.

## Learning-model paper account
A second simulated account runs the walk-forward ML model from [results/MODEL.md](results/MODEL.md) live.
It retrains every week, after the Friday close, on 24 inputs per currency. Then it goes long the 3 currencies
predicted strongest and short the 3 weakest (dollar-neutral, 10% volatility target). Every prediction is logged
to `paper_ml/predictions.csv` and scored once its week ends, so you can compare the live accuracy with the
backtest. The backtest showed no edge, so judge it only after ~26 scored weeks. `paper_ml/REPORT.md` also
shows the trend account over the same period. Unlike the trend account, it books interest carry.

## Setup
```bash
pip install -r requirements.txt
python -m pytest -q
```

## Commands
| Command | What it does |
|---|---|
| `python -m fxbot backtest` | Downloads full history and writes `results/BACKTEST.md` (both modes, both halves, with/without costs, single-rule and per-pair grids) |
| `python -m fxbot signals` | Prints today's blend per pair, no trading |
| `python -m fxbot paper run` | One daily paper step: mark, charge financing, trade on a new signal day. Safe to re-run |
| `python -m fxbot paper status` | Account summary and positions |
| `python -m fxbot paper report` | Writes `paper/REPORT.md` and an equity chart |
| `python -m fxbot ml run` / `status` / `report` | **Learning-model paper account** (`paper_ml/`): retrains LightGBM every week on all past weeks, trades long 3 / short 3 currencies, logs and scores every prediction live |

Settings (pairs, spreads, mode, band, volatility target, leverage caps) are in `config.toml`.

## Deployment
`.github/workflows/paper-trading.yml` runs at 00:30 UTC Tuesday to Saturday, after each weekday's close.
It runs `paper run` and `paper report`, then commits `paper/` back to `main`. Use **Actions → Daily FX paper
trading → Run workflow** to start it right away (tick *backtest* to refresh `results/` too). The workflow
needs **Settings → Actions → General → Workflow permissions → Read and write**. No secrets are needed.

## Layout
```
fxbot/data.py      Yahoo daily closes: closed days only, weekends dropped, bad-tick filter
fxbot/strategy.py  rules, blend, band, vol sizing, backtest, performance stats
fxbot/paper.py     paper account (multi-currency P&L in USD, financing, cost model)
fxbot/report.py    paper/REPORT.md + SVG chart, results/BACKTEST.md
fxbot/factors.py   research: carry / momentum / value / trend sleeves with interest carry
fxbot/model.py     learning model: features, walk-forward training, predictions
fxbot/ml_paper.py  learning-model paper account (weekly retrain, live scorecard)
fxbot/rates.py     research: FRED short-term rates per currency (lagged, no lookahead)
research/          scripts behind results/RESEARCH.md
tests/             no-lookahead, band, data-cleaning and paper-accounting tests
```
