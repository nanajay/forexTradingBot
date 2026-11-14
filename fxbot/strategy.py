"""Trend-following on daily FX closes, ported from TradingBot's BTC/ETH "blend".

Rules (same fixed parameters as the crypto bot, not tuned to FX data):
  sma_N : up if close > N-day simple moving average
  mom_N : up if the N-day return > 0
  blend : average of sma_{20,50,100,200} and mom_{30,90,180}

  long_only  : up = 1, down = 0   -> blend 0..1 in 1/7 steps (identical to the crypto bot)
  long_short : up = +1, down = -1 -> blend -1..+1 in 2/7 steps (FX can trend either way)

Execution model (no hindsight), as in the crypto backtest:
  * signals use closes up to day t; the new position is traded at day t's close and
    earns day t+1's return;
  * a no-trade band skips small signal changes to limit cost churn;
  * every change in position pays half the spread + slippage on the traded notional;
  * open positions pay a financing (rollover) markup on gross notional.

Sizing is the one deliberate difference: a currency pair moves ~10x less than BTC, so
each pair is scaled to a volatility target, measured when the position is (re)set and
held until the signal next changes (no daily vol-driven churn).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

SMA_SET = (20, 50, 100, 200)
MOM_SET = (30, 90, 180)
DAYS_PER_YEAR = 252


def rule_weights(close: pd.Series, rule: str, mode: str = "long_short",
                 sma: tuple = SMA_SET, mom: tuple = MOM_SET) -> pd.Series:
    down = -1.0 if mode == "long_short" else 0.0
    if rule.startswith("sma_"):
        n = int(rule[4:])
        avg = close.rolling(n).mean()
        return pd.Series(np.where(close > avg, 1.0, down), index=close.index).where(avg.notna())
    if rule.startswith("mom_"):
        n = int(rule[4:])
        r = close / close.shift(n) - 1
        return pd.Series(np.where(r > 0, 1.0, down), index=close.index).where(r.notna())
    if rule == "blend":
        parts = [rule_weights(close, f"sma_{n}", mode) for n in sma]
        parts += [rule_weights(close, f"mom_{n}", mode) for n in mom]
        return pd.concat(parts, axis=1).mean(axis=1, skipna=False)
    if rule == "hold":
        return pd.Series(1.0, index=close.index)
    raise ValueError(rule)


def band_step(target: float, cur: float, band: float, mode: str) -> float:
    """One no-trade-band decision. `band` is a fraction of the signal range."""
    if math.isnan(target):
        return cur
    width = band * (2.0 if mode == "long_short" else 1.0)
    extremes = (-1.0, 0.0, 1.0) if mode == "long_short" else (0.0, 1.0)
    crosses_zero = mode == "long_short" and target * cur < 0
    if abs(target - cur) >= width or (target in extremes and target != cur) or crosses_zero:
        return target
    return cur


def apply_band(target: pd.Series, band: float, mode: str) -> pd.Series:
    out, cur = np.empty(len(target)), 0.0
    for i, t in enumerate(target.to_numpy()):
        cur = band_step(float(t), cur, band, mode)
        out[i] = cur
    return pd.Series(out, index=target.index)


def realized_vol(close: pd.Series, lookback: int) -> pd.Series:
    return close.pct_change().rolling(lookback).std() * math.sqrt(DAYS_PER_YEAR)


def vol_scale(vol: float, n_pairs: int, sizing: dict) -> float:
    """Notional (x equity) for a full-signal position in one pair."""
    if not vol or math.isnan(vol) or vol <= 0:
        return 0.0
    per_pair = sizing["vol_target"] / math.sqrt(n_pairs)
    return min(per_pair / vol, sizing["max_pair_leverage"])


def cap_gross(weights: dict[str, float], max_gross: float) -> dict[str, float]:
    gross = sum(abs(w) for w in weights.values())
    if gross > max_gross:
        return {p: w * max_gross / gross for p, w in weights.items()}
    return weights


def target_weights(closes: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Banded signal and final weight (notional / equity, signed) per pair per day.
    The vol scale is fixed when the banded signal changes and held until the next change."""
    st, sz = cfg["strategy"], cfg["sizing"]
    mode = st["mode"]
    n = closes.shape[1]
    sig = pd.DataFrame({p: apply_band(rule_weights(closes[p], "blend", mode,
                                                   tuple(st["sma"]), tuple(st["mom"])),
                                      st["band"], mode)
                        for p in closes})
    vol = closes.apply(lambda c: realized_vol(c, sz["vol_lookback"]))
    w = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for p in closes:
        s, v = sig[p].to_numpy(), vol[p].to_numpy()
        out, scale, prev = np.zeros(len(s)), 0.0, 0.0
        for i in range(len(s)):
            if s[i] != prev or (s[i] != 0 and scale == 0.0):
                scale = vol_scale(v[i], n, sz)
                prev = s[i]
            out[i] = s[i] * scale
        w[p] = out
    gross = w.abs().sum(axis=1)
    over = gross > sz["max_gross_leverage"]
    w.loc[over] = w.loc[over].mul(sz["max_gross_leverage"] / gross[over], axis=0)
    return sig, w


def backtest_weights(closes: pd.DataFrame, weights: pd.DataFrame, cost: dict[str, float],
                     financing_bps_year: float) -> pd.DataFrame:
    """Weight decided at close t earns the return from t to t+1 (a short earns minus it).
    Weights are treated as a constant fraction of equity between changes."""
    rets = closes.pct_change().fillna(0.0)
    w = weights.fillna(0.0)
    held = w.shift(1).fillna(0.0)
    traded = w.diff().abs()
    traded.iloc[0] = w.iloc[0].abs()
    costs = sum(traded[p] * cost[p] for p in w.columns)
    financing = held.abs().sum(axis=1) * financing_bps_year / 1e4 / DAYS_PER_YEAR
    gross = (held * rets).sum(axis=1)
    return pd.DataFrame({"ret": gross - costs - financing, "gross": gross,
                         "turnover": traded.sum(axis=1), "cost": costs, "financing": financing,
                         "gross_leverage": held.abs().sum(axis=1)})


def perf(daily: pd.Series, res: pd.DataFrame | None = None) -> dict:
    eq = (1 + daily).cumprod()
    years = len(daily) / DAYS_PER_YEAR
    cagr = eq.iloc[-1] ** (1 / years) - 1 if eq.iloc[-1] > 0 else -1.0
    dd = eq / eq.cummax() - 1
    sd = daily.std()
    yearly = (1 + daily).groupby(daily.index.year).prod() - 1
    out = {"total_%": round((eq.iloc[-1] - 1) * 100, 1), "CAGR_%": round(cagr * 100, 1),
           "maxDD_%": round(dd.min() * 100, 1), "vol_%": round(sd * math.sqrt(DAYS_PER_YEAR) * 100, 1),
           "sharpe": round(daily.mean() / sd * math.sqrt(DAYS_PER_YEAR), 2) if sd > 0 else 0.0,
           "worst_year_%": round(yearly.min() * 100, 1),
           "best_year_%": round(yearly.max() * 100, 1)}
    if res is not None:
        out["avg_gross_lev"] = round(res["gross_leverage"].mean(), 2)
        out["trades_per_yr"] = round(float((res["turnover"] > 0).sum() / years), 1)
        out["costs_%_yr"] = round((res["cost"] + res["financing"]).sum() / years * 100, 2)
    return out


def costs_from_cfg(cfg: dict) -> dict[str, float]:
    from .config import pair_cost
    return {p: pair_cost(cfg, p) for p in cfg["pairs"]}


def run(closes: pd.DataFrame, cfg: dict, start: str | None = None,
        end: str | None = None) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    _, w = target_weights(closes, cfg)
    sl = slice(start or cfg["backtest"]["start"], end)
    res = backtest_weights(closes.loc[sl], w.loc[sl], costs_from_cfg(cfg),
                           cfg["costs"]["financing_bps_year"])
    return res, perf(res["ret"], res), w.loc[sl]
