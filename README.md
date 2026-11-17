# Forex Trend Bot

A forex trading bot for the seven major USD currency pairs. It runs two strategies, a **forex trend strategy**
and a **forex learning model**, each on a simulated paper account and an OANDA **practice** (demo-money) account,
every weekday via GitHub Actions. There is no real-money trading: the broker client can only reach OANDA's
practice server.

**📊 Live status: [REPORT.md](REPORT.md)**: both strategies at a glance, today's trades and the go-live check
(updated every weekday). Strategy pages: [📈 trend](paper/REPORT.md) · [🤖 learning model](paper_ml/REPORT.md).

> **Read this first: the strategy has not worked on FX since 2015.** Backtested on daily closes from 2004 to
> 2026, it made about +4% a year from 2004 to 2014 and lost about −7% a year from 2015 to 2026 after costs
> (−5% a year **before** costs). Every single rule loses over 2015–2026, so this isn't one unlucky parameter.
> Full numbers are in [results/BACKTEST.md](results/BACKTEST.md). Carry, momentum, value and mixes were also
> tested ([results/RESEARCH.md](results/RESEARCH.md)): none made money out of sample. The paper account is here to watch it live,
> not as a reason to fund it.

## The forex trend strategy
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

## OANDA practice accounts (demo money, real broker)
Optionally, each paper account is mirrored onto its own **OANDA practice account**. That gives real broker
prices, spreads, financing and order handling, still with fake money. `fxbot/oanda.py` can only reach
`api-fxpractice.oanda.com`, and no setting points it at a live account. Safety checks in `config.toml [practice]`:
market closed, stale paper account, bad price, wide spread, leverage and order-size caps, a halt at −50% NAV.

To turn it on:
1. Open a free OANDA practice account, add a second sub-account, and generate a personal access token.
2. In GitHub, go to **Settings → Secrets and variables → Actions** and add the secrets `OANDA_API_TOKEN`,
   `OANDA_ACCOUNT_TREND` and `OANDA_ACCOUNT_ML` (account ids look like `101-001-1234567-001`).
3. The next workflow run trades both practice accounts and commits `practice_trend/` and `practice_ml/`.

Commands: `python -m fxbot practice accounts` lists the token's accounts.
`python -m fxbot practice run --strategy trend|ml [--dry-run]` places (or with `--dry-run`, only plans) orders.
`python -m fxbot practice status --strategy trend|ml` compares the real costs with the paper assumptions.

## Go-live gate
`python -m fxbot gate` scores each strategy against fixed criteria and writes [results/GATE.md](results/GATE.md)
on every run. The criteria: at least 26 weeks on OANDA practice, a profit after all costs (and for the learning
model, a statistically significant live prediction IC), real costs within 25% of the assumptions, practice
tracking paper within 3 points, no missed runs, mismatches or halts, and a drawdown no deeper than −20%.
Thresholds are in `config.toml [gate]`. Each strategy is **READY** only if every check passes, **WAIT** while data
is too thin, otherwise **NOT READY**. READY means "eligible for a tiny live trial", nothing more.

## Alerts
After every weekday run, the workflow sends one **daily summary**:
* For each of the 4 accounts (trend and learning model, each on paper and OANDA practice): today's trades,
  today's change, the total account value and the total change since the start.
* The go-live gate verdicts, flagged when they change.
* **Problems first, sent as high priority:** a failed step, a position mismatch, a halt, a rejected order or
  a crash.

If a weekday passes with no message, the workflow itself didn't run. Add either or both GitHub secrets:
* `ALERT_NTFY_TOPIC`: push notifications to your phone via the free [ntfy](https://ntfy.sh) app. Subscribe to a
  long, random topic name; anyone who knows the name can read the messages.
* `ALERT_WEBHOOK_URL`: a Slack or Discord incoming-webhook URL.

Messages never contain account ids or tokens. To preview the format, use **Actions → Daily FX paper trading →
Run workflow → "Send a test alert"**.

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
`.github/workflows/paper-trading.yml` runs at 02:17 UTC Monday to Friday, while the FX market is open (Monday's run acts on Friday's close).
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
fxbot/oanda.py     OANDA v20 client, practice server only
fxbot/practice.py  mirrors a paper account onto an OANDA practice account, with safety checks
fxbot/gate.py      go-live gate -> results/GATE.md
fxbot/alerts.py    phone / chat alerts on problems, Monday check-in
fxbot/rates.py     research: FRED short-term rates per currency (lagged, no lookahead)
research/          scripts behind results/RESEARCH.md
tests/             no-lookahead, band, data-cleaning and paper-accounting tests
```
