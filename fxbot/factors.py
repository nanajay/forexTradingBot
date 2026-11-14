"""FX factor strategies on currency exposures vs USD.

Everything is expressed as a daily matrix of exposures, one column per non-USD currency
(EUR, GBP, JPY, AUD, CAD, CHF, NZD): +0.5 = long that currency vs USD for 50% of equity.
A dollar-neutral strategy has exposures that sum to zero, so it carries no net USD bet.

Return of holding currency X vs USD for one day:
    spot move of X in USD  +  (rate_X - rate_USD) / 252   (the interest-rate carry)
minus a broker financing markup on gross exposure, minus spread costs on changes.

Strategies (parameters fixed from the FX literature, not tuned here):
  trend    : the crypto bot's 7-rule blend per currency vs USD (time-series, has a USD bet)
  carry    : rank all 8 currencies (USD included) by 3-month rate; long top 3, short bottom 3
  momentum : the same ranking on 12-month spot return (cross-sectional momentum)
  value    : the same ranking on minus the 5-year spot return (long-term reversal, a price-only value proxy)
  combo    : equal-risk mix of the sleeves passed in
Cross-sectional sleeves rebalance weekly (Friday close) to keep turnover down.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .strategy import DAYS_PER_YEAR, apply_band, rule_weights

CCY_OF = {"EUR/USD": "EUR", "GBP/USD": "GBP", "USD/JPY": "JPY", "AUD/USD": "AUD",
          "USD/CAD": "CAD", "USD/CHF": "CHF", "NZD/USD": "NZD"}


def ccy_prices(closes: pd.DataFrame) -> pd.DataFrame:
    """USD value of one unit of each currency (USD/XXX pairs inverted)."""
    out = {}
    for pair, ccy in CCY_OF.items():
        if pair in closes:
            out[ccy] = closes[pair] if pair.endswith("/USD") else 1.0 / closes[pair]
    return pd.DataFrame(out)


def rate_diff(rates: pd.DataFrame, index: pd.DatetimeIndex, ccys: list[str]) -> pd.DataFrame:
    """Annual rate of each currency minus the USD rate, as a decimal, on `index` days."""
    r = rates.reindex(rates.index.union(index)).ffill().reindex(index)
    return pd.DataFrame({c: (r[c] - r["USD"]) / 100 for c in ccys}, index=index)


def xs_rank_weights(score: pd.DataFrame, n_long: int = 3, n_short: int = 3) -> pd.DataFrame:
    """Score includes a USD column. Long the top n, short the bottom n (equal weights, +1/-1
    in total each side), then drop USD: the remaining exposures vs USD are what you trade."""
    w = pd.DataFrame(0.0, index=score.index, columns=score.columns)
    valid = score.notna().sum(axis=1) >= n_long + n_short
    ranks = score.rank(axis=1, ascending=False, method="first")
    k = score.notna().sum(axis=1)
    w[ranks.le(n_long, axis=0)] = 1.0 / n_long
    w[ranks.gt(k - n_short, axis=0) & score.notna()] = -1.0 / n_short
    w[~valid] = 0.0
    # Currency weights summing to zero (USD included) are exactly the same book as
    # exposures w_X vs USD for every non-USD currency X; the USD leg absorbs the rest.
    return w.drop(columns="USD")


def weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Hold Friday's (last trading day of the week) value until the next one."""
    idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
    wk = pd.Series(idx.to_period("W-FRI"), index=df.index)
    last = wk != wk.shift(-1)
    return df.where(last, np.nan).ffill()


def vol_target(expo: pd.DataFrame, rets: pd.DataFrame, target: float, lookback: int = 120,
               max_gross: float = 4.0) -> pd.DataFrame:
    """Scale a sleeve so its ex-ante volatility (from trailing covariance) hits `target`.
    The scale is recomputed weekly only, to avoid daily churn."""
    scale = pd.Series(np.nan, index=expo.index)
    cov_src = rets.fillna(0.0)
    fridays = weekly(pd.DataFrame({"x": np.arange(len(expo))}, index=expo.index))["x"]
    for i in np.unique(fridays.dropna().astype(int)):
        if i < lookback:
            continue
        cov = cov_src.iloc[i - lookback + 1:i + 1].cov().to_numpy() * DAYS_PER_YEAR
        w = expo.iloc[i].fillna(0.0).to_numpy()
        v = math.sqrt(max(w @ cov @ w, 0.0))
        scale.iloc[i] = target / v if v > 1e-9 else 0.0
    out = expo.mul(scale.ffill().fillna(0.0), axis=0)
    gross = out.abs().sum(axis=1)
    over = gross > max_gross
    out.loc[over] = out.loc[over].mul(max_gross / gross[over], axis=0)
    return out


def sleeve_trend(px: pd.DataFrame, mode: str = "long_short", band: float = 0.15) -> pd.DataFrame:
    return pd.DataFrame({c: apply_band(rule_weights(px[c], "blend", mode), band, mode) for c in px})


def sleeve_carry(diff: pd.DataFrame) -> pd.DataFrame:
    score = diff.copy()
    score["USD"] = 0.0
    score[diff.isna().all(axis=1)] = np.nan
    return weekly(xs_rank_weights(score))


def sleeve_momentum(px: pd.DataFrame, days: int = 252) -> pd.DataFrame:
    score = np.log(px / px.shift(days))
    score["USD"] = 0.0
    return weekly(xs_rank_weights(score))


def sleeve_value(px: pd.DataFrame, days: int = 5 * 252) -> pd.DataFrame:
    score = -np.log(px / px.shift(days))
    score["USD"] = 0.0
    return weekly(xs_rank_weights(score))


def backtest(expo: pd.DataFrame, px: pd.DataFrame, diff: pd.DataFrame, cost: dict[str, float],
             financing_bps_year: float) -> pd.DataFrame:
    """Exposure decided at close t earns day t+1's spot move plus carry."""
    spot = px.pct_change().fillna(0.0)
    carry = diff.fillna(0.0) / DAYS_PER_YEAR
    held = expo.shift(1).fillna(0.0)
    traded = expo.fillna(0.0).diff().abs()
    traded.iloc[0] = expo.iloc[0].fillna(0.0).abs()
    costs = sum(traded[c] * cost[c] for c in expo.columns)
    fin = held.abs().sum(axis=1) * financing_bps_year / 1e4 / DAYS_PER_YEAR
    spot_pnl = (held * spot).sum(axis=1)
    carry_pnl = (held * carry).sum(axis=1)
    return pd.DataFrame({"ret": spot_pnl + carry_pnl - costs - fin, "spot": spot_pnl,
                         "carry": carry_pnl, "cost": costs, "financing": fin,
                         "turnover": traded.sum(axis=1), "gross_leverage": held.abs().sum(axis=1),
                         "net_usd": -held.sum(axis=1)})
