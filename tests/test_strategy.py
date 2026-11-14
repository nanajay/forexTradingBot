import numpy as np
import pandas as pd

from fxbot import strategy as S
from fxbot.config import load_config


def series(vals, start="2020-01-01"):
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals), tz="UTC"), dtype=float)


def test_no_lookahead():
    rng = np.random.default_rng(0)
    c = series(np.exp(np.cumsum(rng.normal(0, 0.005, 600))))
    full = S.rule_weights(c, "blend")
    cut = S.rule_weights(c.iloc[:400], "blend")
    pd.testing.assert_series_equal(full.iloc[:400], cut)


def test_blend_values_long_short_and_long_only():
    up = series(np.linspace(1.0, 2.0, 300))
    down = series(np.linspace(2.0, 1.0, 300))
    assert S.rule_weights(up, "blend", "long_short").iloc[-1] == 1.0
    assert S.rule_weights(down, "blend", "long_short").iloc[-1] == -1.0
    assert S.rule_weights(down, "blend", "long_only").iloc[-1] == 0.0
    assert np.isnan(S.rule_weights(up, "blend").iloc[150])     # 200-day SMA not ready yet


def test_band():
    # long_short: effective band 0.30, single 2/7 step (0.286) is skipped
    assert S.band_step(3 / 7, 1 / 7, 0.15, "long_short") == 1 / 7
    assert S.band_step(5 / 7, 1 / 7, 0.15, "long_short") == 5 / 7
    assert S.band_step(-1 / 7, 1 / 7, 0.15, "long_short") == -1 / 7     # crossing zero always trades
    assert S.band_step(1.0, 5 / 7, 0.15, "long_short") == 1.0           # full position always trades
    # long_only matches the crypto bot: 1/7 step blocked, move to 0 always goes through
    assert S.band_step(3 / 7, 2 / 7, 0.15, "long_only") == 2 / 7
    assert S.band_step(0.0, 1 / 7, 0.15, "long_only") == 0.0
    assert S.band_step(float("nan"), 0.5, 0.15, "long_only") == 0.5


def test_backtest_short_profits_when_price_falls_and_costs_apply():
    c = pd.DataFrame({"EUR/USD": [1.0, 0.9, 0.81]}, index=pd.bdate_range("2024-01-01", periods=3))
    w = pd.DataFrame({"EUR/USD": [-1.0, -1.0, -1.0]}, index=c.index)
    res = S.backtest_weights(c, w, {"EUR/USD": 0.001}, 0.0)
    assert abs(res["ret"].iloc[0] + 0.001) < 1e-12       # entry cost on day 0
    assert abs(res["ret"].iloc[1] - 0.1) < 1e-12
    assert abs(res["ret"].iloc[2] - 0.1) < 1e-12


def test_weights_respect_leverage_caps():
    cfg = load_config()
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2015-01-01", periods=800, tz="UTC")
    closes = pd.DataFrame({p: np.exp(np.cumsum(rng.normal(0.0003, 0.002, 800))) for p in cfg["pairs"]}, index=idx)
    _, w = S.target_weights(closes, cfg)
    assert w.abs().max().max() <= cfg["sizing"]["max_pair_leverage"] + 1e-9
    assert w.abs().sum(axis=1).max() <= cfg["sizing"]["max_gross_leverage"] + 1e-9
