# Refining the FX strategy: what was tried and what held up (2026-11-14)

**Short answer: nothing tried here is worth trading.** The crypto trend rules fail on FX majors after 2014.
None of the standard FX alternatives (carry, cross-sectional momentum, value) or their mixes made money
from 2015 to 2026 after realistic costs. The live paper bot is unchanged.

## Method (fixed before looking at results)
* Universe: the 8 major currencies (USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD), traded through the 7 USD pairs.
* Candidates from the FX research literature, all with standard parameters. Nothing was tuned:
  * **trend:** the crypto bot's 7-rule blend per currency vs USD (long/short).
  * **carry:** long the 3 highest-yielding currencies, short the 3 lowest (USD included in the ranking).
  * **momentum:** the same ranking on 12-month return.
  * **value:** the same ranking on minus the 5-year return (a price-only stand-in for purchasing-power value).
  * **equal-risk mixes** of the above.
* Each one is scaled to 10% yearly volatility, using the last 120 days' covariance and recomputed weekly.
  Ranking strategies rebalance weekly.
* **Returns now include interest carry:** holding a currency earns its rate minus the USD rate. Rates are the
  OECD 3-month interbank rates from FRED, extended with €STR and SONIA where the OECD series stops. Each month's
  value is used only from two months later, to allow for publication delay. The first backtest
  (`BACKTEST.md`) left carry out.
* Costs: half the spread + 0.5 bp per trade, plus a 0.5%/yr broker financing markup on gross exposure.
* **Pick on 2004–2014 only, judge on 2015–2026.**

## Results after costs (`python research/compare.py`)

| Strategy | Sharpe 2004–14 | CAGR 2004–14 | Sharpe 2015–26 | CAGR 2015–26 | Max DD 2015–26 |
|---|---:|---:|---:|---:|---:|
| trend (crypto rules) | 0.23 | +2.0% | −0.27 | −3.5% | −37% |
| carry | 0.09 | +0.4% | 0.00 | −0.5% | −34% |
| momentum 12m | −0.07 | −1.1% | −0.28 | −3.6% | −35% |
| value (5y reversal) | 0.05 | +0.1% | −0.17 | −2.5% | −36% |
| carry + trend + value | 0.40 | +3.8% | −0.17 | −3.5% | −48% |
| carry + value | 0.15 | +1.1% | −0.11 | −2.1% | −36% |
| **all four (best 2004–14)** | **0.41** | +4.0% | **−0.15** | −2.8% | −42% |

The rule picks "all four", the best mix on 2004–2014. It lost money out of sample.

## Before costs (`python research/gross.py`): is there any edge to save?

| Sleeve | Sharpe 2004–14 | Sharpe 2015–26 | Sharpe 2019–26 |
|---|---:|---:|---:|
| trend | 0.28 | −0.34 | −0.28 |
| carry | 0.19 | 0.10 | 0.50 |
| momentum | −0.02 | −0.22 | −0.05 |
| value | 0.18 | 0.05 | 0.07 |

* Trend and momentum have **negative** returns before costs since 2015, so no cost refinement can fix them.
* Carry is the only sleeve with a positive edge: about +1%/yr before costs at 10% volatility since 2015. It
  needs ~2.8x gross leverage to reach that volatility, so a 0.5%/yr financing markup costs ~1.4%/yr and wipes
  it out. It also carries the classic carry-crash risk (−24% in 2008, −9% in 2015 at the CHF de-peg).
* These findings match published work: G10 FX trend, momentum and carry all had a weak decade after 2014.

## What this means
* **Don't fund any of these.** The paper bot keeps tracking the original crypto-rules port so you can watch it live.
* More rule tweaks on the same data would just fit 2015–2026 noise. That period is the test, so it can't also
  be used for tuning.
* Things that could change the picture, each its own project and each needing new data:
  1. **Emerging-market carry** (MXN, ZAR, BRL, TRY…): a much larger rate premium, but crash risk and costs are
     larger too.
  2. **Execution at institutional costs** (financing markup ~0.1%/yr): would make the G10 carry sleeve
     marginally positive, roughly Sharpe 0.2–0.3 since 2015.
  3. **Intraday or event strategies** (around central-bank decisions): need tick or minute data, which this
     bot doesn't have.
