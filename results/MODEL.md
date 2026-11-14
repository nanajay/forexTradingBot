# Predictive model for FX: walk-forward test (2026-11-14)

**Verdict: no predictive power.** A machine-learning model on 24 standard FX inputs, retrained every year and
tested only on the following year, predicts next week's currency moves **no better than the same model trained
on shuffled (meaningless) labels**. Don't trade it.

## The model, step by step (`fxbot/model.py`, run with `python research/model_walkforward.py`)
1. **Data:** daily closes for EUR, GBP, JPY, AUD, CAD, CHF and NZD vs USD (Yahoo, bad ticks removed);
   3-month interest rates per currency (FRED, each month's value used only from two months later); VIX and
   the S&P 500.
2. **Features:** 24 per currency, taken at each Friday's close and using past data only:
   * momentum over 1/4/12/24/50 weeks, scaled by volatility;
   * distance from the 50- and 200-day averages, RSI-14, the forex trend strategy's 7-rule blend;
   * volatility level and 20/60-day volatility ratio;
   * interest carry and its 3- and 6-month change, plus cross-sectional ranks of momentum and carry;
   * broad USD move, VIX level and 4-week change, S&P 500 1- and 4-week return, carry × VIX change.
3. **Target:** next week's return (spot + carry) ÷ volatility. *Relative*: minus that week's average across the
   7 currencies (which currency beats the others). *Absolute*: the direction vs USD.
4. **Models:** ridge regression and LightGBM (300 small trees, heavy regularization). Settings fixed up front.
5. **Walk-forward:** for each year Y from 2008, train on all weeks before Y. The last week before Y is left out
   so no training label overlaps the test year. Then predict Y.
6. **Portfolio:**
   * Relative target: each Friday, long the 3 best-predicted currencies and short the 3 worst.
   * Absolute target: each position proportional to its prediction.
   * Both: scaled to 10% volatility, with full spread and financing costs.
7. **Controls:**
   * The identical pipeline trained on shuffled labels (3 seeds), as a luck baseline.
   * A leak check: a feature that weakly peeks at the future gives IC 0.185, so the pipeline can find real
     signal when there is some.

## Results
IC = average weekly rank correlation between prediction and the actual outcome. Useful FX models are around
0.05 or more.

| Target | Model | IC 2008–14 | IC 2015–26 | Net Sharpe 2015–26 | Shuffled-label net Sharpe 2015–26 (3 seeds) |
|---|---|---:|---:|---:|---|
| relative | ridge | −0.042 | −0.003 | −0.26 | −0.06, −0.63, −0.75 |
| relative | LightGBM | −0.026 | +0.014 | −0.25 | −0.37, −0.39, −0.51 |
| absolute | ridge | −0.054 | −0.000 | −0.17 | −0.22, −0.19, −0.27 |
| absolute | LightGBM | −0.035 | −0.007 | −0.44 | −0.12, −0.26, −0.04 |

Full table: `research/model_results.csv`. Weekly rebalancing costs 2–4% a year, so even a small real edge would
be needed just to break even. There is none.

## Single inputs, 2015–2026 (for information only)
* **Carry:** IC +0.053 (t 2.7). Partly mechanical, because the target includes the interest earned. Traded as
  a strategy it's about break-even after costs (see `RESEARCH.md`).
* **4-week reversal:** IC −0.043 (t −2.3). This was found by scanning 24 inputs on the test period, where
  one result this strong is expected by chance. It's a hypothesis to check on new data, not a signal.

## Why this is the expected result
Major currency pairs are the most liquid, most heavily traded markets in the world. Public price, rate and
sentiment data is already priced in within minutes. Published academic and industry evidence finds little
predictability at daily-to-weekly horizons after costs since the mid-2010s.
