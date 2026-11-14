"""Predictive model for FX: weekly, panel of 7 currencies vs USD, walk-forward.

Step by step:
  1. Data     daily FX closes, short-term rates per currency (lagged 2 months), VIX and S&P 500.
  2. Features ~25 causal inputs per currency on each Friday close: multi-horizon momentum (vol-scaled),
              distance from moving averages, RSI, the crypto trend blend, volatility regime, interest
              carry and its 3/6-month change, cross-sectional ranks, broad USD move, risk sentiment.
  3. Target   next week's return of the currency vs USD (spot + carry), divided by its volatility.
              "relative": minus the average of all 7 that week (what beats the others, dollar-neutral).
              "absolute": as is (direction vs USD).
  4. Models   ridge regression (linear baseline) and LightGBM (small, heavily regularized trees).
              Hyperparameters fixed up front, not searched.
  5. Walk-forward: for each test year Y, train on every week up to Dec Y-1 minus a 1-week embargo
              (so no training label overlaps the test year), predict all of year Y, move on.
  6. Portfolio relative: long the 3 best-predicted currencies, short the 3 worst. absolute: position
              proportional to the prediction. Scaled to 10% volatility, held for the week, full costs.
  7. Controls the same pipeline trained on shuffled labels (pure luck), several seeds.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import factors as F
from .strategy import DAYS_PER_YEAR, rule_weights

H = 5   # trading days in the prediction horizon (one week)


def _rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def fridays(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    idx = index.tz_localize(None) if index.tz is not None else index
    wk = pd.Series(idx.to_period("W-FRI"), index=index)
    return index[(wk != wk.shift(-1)).to_numpy()]


def build_panel(px: pd.DataFrame, diff: pd.DataFrame, vix: pd.Series, spx: pd.Series) -> pd.DataFrame:
    """One row per (Friday, currency): features known at that Friday's close + next-week targets."""
    lp = np.log(px)
    dret = px.pct_change()
    vol60 = dret.rolling(60).std()                      # daily vol
    vol20 = dret.rolling(20).std()
    fwd = (dret.shift(-1).rolling(H).sum().shift(-(H - 1))        # days t+1..t+H spot
           + diff.shift(-1).rolling(H).sum().shift(-(H - 1)) / DAYS_PER_YEAR)   # + carry
    feats: dict[str, pd.DataFrame] = {}
    for h in (5, 20, 60, 120, 250):
        feats[f"mom_{h}"] = (lp - lp.shift(h)) / (vol60 * np.sqrt(h))
    for n in (50, 200):
        feats[f"dist_sma{n}"] = (lp - np.log(px.rolling(n).mean())) / (vol60 * np.sqrt(n))
    feats["rsi14"] = px.apply(_rsi)
    feats["trend_blend"] = px.apply(lambda c: rule_weights(c, "blend", "long_short"))
    feats["vol_ratio"] = vol20 / vol60
    feats["vol_level"] = vol60 * np.sqrt(DAYS_PER_YEAR)
    feats["carry"] = diff
    feats["carry_chg63"] = diff - diff.shift(63)
    feats["carry_chg126"] = diff - diff.shift(126)
    for k in ("mom_20", "mom_60", "mom_250", "carry"):
        feats[f"xs_rank_{k}"] = feats[k].rank(axis=1, pct=True)
    usd = -(lp - lp.shift(20)).mean(axis=1)            # broad USD move over 4 weeks
    vix_a = vix.reindex(px.index).ffill(limit=3)
    spx_a = spx.reindex(px.index).ffill(limit=3)
    market = pd.DataFrame({"usd_20": usd,
                           "vix": vix_a,
                           "vix_chg20": np.log(vix_a / vix_a.shift(20)),
                           "spx_5": np.log(spx_a / spx_a.shift(5)),
                           "spx_20": np.log(spx_a / spx_a.shift(20))}, index=px.index)
    fr = fridays(px.index)
    rows = []
    for c in px.columns:
        d = pd.DataFrame({k: v[c] for k, v in feats.items()}, index=px.index)
        d = d.join(market)
        # risk-on/off interacts with carry: high yielders fall when VIX jumps
        d["carry_x_vixchg"] = d["carry"] * d["vix_chg20"]
        d["y_abs"] = fwd[c] / (vol60[c] * np.sqrt(H))
        d["ccy"] = c
        rows.append(d.loc[fr])
    panel = pd.concat(rows).reset_index(names="date").sort_values(["date", "ccy"])
    panel["y_rel"] = panel["y_abs"] - panel.groupby("date")["y_abs"].transform("mean")
    return panel


FEATURES_EXCLUDE = {"date", "ccy", "y_abs", "y_rel"}


def feature_cols(panel: pd.DataFrame) -> list[str]:
    return [c for c in panel.columns if c not in FEATURES_EXCLUDE]


def make_model(kind: str, seed: int = 0):
    if kind == "ridge":
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        return make_pipeline(StandardScaler(), Ridge(alpha=50.0))
    if kind == "lgbm":
        import lightgbm as lgb
        return lgb.LGBMRegressor(n_estimators=300, learning_rate=0.02, num_leaves=8, min_child_samples=200,
                                 subsample=0.7, subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0,
                                 random_state=seed, verbose=-1)
    raise ValueError(kind)


def walk_forward(panel: pd.DataFrame, target: str, kind: str, first_test_year: int = 2008,
                 shuffle_seed: int | None = None) -> pd.DataFrame:
    """Out-of-sample predictions for every test year, each from a model trained only on the past."""
    cols = feature_cols(panel)
    data = panel.dropna(subset=cols + [target]).copy()
    # clip extreme feature/target values (bad prints, crisis days) so they can't dominate a fit
    data[target] = data[target].clip(-4, 4)
    out = []
    last_year = int(data["date"].dt.year.max())
    for y in range(first_test_year, last_year + 1):
        start = pd.Timestamp(f"{y}-01-01", tz="UTC")
        train = data[data["date"] < start - pd.Timedelta(days=7)]     # embargo: labels end before Y
        test = data[(data["date"] >= start) & (data["date"] < pd.Timestamp(f"{y + 1}-01-01", tz="UTC"))]
        if test.empty or len(train) < 1000:
            continue
        ytr = train[target].to_numpy()
        if shuffle_seed is not None:
            ytr = np.random.default_rng(shuffle_seed + y).permutation(ytr)
        m = make_model(kind, seed=shuffle_seed or 0)
        m.fit(train[cols].to_numpy(), ytr)
        t = test[["date", "ccy", "y_abs", "y_rel"]].copy()
        t["pred"] = m.predict(test[cols].to_numpy())
        out.append(t)
    # also score the latest Friday(s) that have no label yet (the live prediction)
    return pd.concat(out, ignore_index=True)


def information_coefficient(preds: pd.DataFrame, target: str) -> pd.Series:
    """Weekly Spearman correlation between prediction and realized target across currencies."""
    def ic(g):
        return g["pred"].rank().corr(g[target].rank()) if g[target].notna().sum() > 3 else np.nan
    return preds.groupby("date")[["pred", target]].apply(ic).dropna()


def positions(preds: pd.DataFrame, target: str, index: pd.DatetimeIndex, ccys: list[str]) -> pd.DataFrame:
    """Weekly predictions -> daily exposures (held from Friday close to the next Friday close)."""
    p = preds.pivot(index="date", columns="ccy", values="pred").reindex(columns=ccys)
    if target == "y_rel":
        score = p.copy()
        rank = score.rank(axis=1, ascending=False, method="first")
        k = score.notna().sum(axis=1)
        w = pd.DataFrame(0.0, index=p.index, columns=ccys)
        w[rank.le(3, axis=0)] = 1 / 3
        w[rank.gt(k - 3, axis=0) & score.notna()] = -1 / 3
    else:
        sd = p.stack().std()
        w = (p / sd).clip(-1, 1).fillna(0.0)
    return w.reindex(index).ffill().fillna(0.0)
