import numpy as np
import pandas as pd

from fxbot import factors as F
from fxbot.rates import usable_rates


def test_xs_rank_long_top_short_bottom_and_dollar_neutral_with_usd():
    idx = pd.bdate_range("2024-01-01", periods=2, tz="UTC")
    score = pd.DataFrame({"EUR": [5, 5], "GBP": [4, 4], "JPY": [-3, -3], "AUD": [3, 3], "CAD": [1, 1],
                          "CHF": [-2, -2], "NZD": [2, 2], "USD": [0, 0]}, index=idx, dtype=float)
    w = F.xs_rank_weights(score)
    row = w.iloc[0]
    assert np.isclose(row[["EUR", "GBP", "AUD"]], 1 / 3).all()
    # bottom three of all eight: JPY, CHF, USD -> USD leg is implicit
    assert np.isclose(row[["JPY", "CHF"]], -1 / 3).all() and row["CAD"] == 0 and row["NZD"] == 0
    assert np.isclose(row.sum(), 1 / 3)            # net long foreign = short USD 1/3


def test_weekly_holds_friday_value():
    idx = pd.bdate_range("2024-01-01", periods=10, tz="UTC")       # Mon 1 Jan .. Fri 12 Jan
    df = pd.DataFrame({"x": np.arange(10.0)}, index=idx)
    out = F.weekly(df)["x"]
    assert np.isnan(out.iloc[0]) and out.iloc[4] == 4 and out.iloc[8] == 4 and out.iloc[9] == 9


def test_rates_publication_lag():
    m = pd.DataFrame({"USD": [5.0, 4.0]}, index=pd.period_range("2024-01", periods=2, freq="M"))
    u = usable_rates(m)
    assert u.index[0] == pd.Timestamp("2024-03-01", tz="UTC")     # January's value usable in March


def test_backtest_includes_carry():
    idx = pd.bdate_range("2024-01-01", periods=253, tz="UTC")
    px = pd.DataFrame({"AUD": 0.7}, index=idx)                     # flat spot
    diff = pd.DataFrame({"AUD": 0.04}, index=idx)                 # AUD yields 4% more than USD
    expo = pd.DataFrame({"AUD": 1.0}, index=idx)
    r = F.backtest(expo, px, diff, {"AUD": 0.0}, 0.0)
    assert abs(r["ret"].sum() - 0.04) < 1e-9
