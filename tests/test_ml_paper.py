from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from fxbot import ml_paper
from fxbot.config import load_config


def make_loaders(cfg, end):
    idx = pd.bdate_range("2012-01-02", end, tz="UTC")
    rng = np.random.default_rng(3)
    closes = pd.DataFrame({p: np.exp(np.cumsum(rng.normal(0, 0.005, len(idx)))) for p in cfg["pairs"]}, index=idx)
    rates = pd.DataFrame({c: 2.0 + i * 0.3 for i, c in enumerate(["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"])},
                         index=pd.date_range("2011-01-01", periods=200, freq="MS", tz="UTC"))
    vix = pd.Series(15 + rng.normal(0, 1, len(idx)), index=idx)
    spx = pd.Series(np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(idx)))), index=idx)

    def cut(now):
        return closes[closes.index < pd.Timestamp(now).normalize()]
    return {"closes": cut, "rates": lambda: rates,
            "market": lambda now: (vix[vix.index < pd.Timestamp(now).normalize()],
                                   spx[spx.index < pd.Timestamp(now).normalize()]),
            "price": lambda sym: float(closes[[p for p in cfg["pairs"] if cfg["pairs"][p][0] == sym][0]].iloc[-1])}


def test_ml_paper_weekly_cycle(tmp_path):
    cfg = load_config()
    loaders = make_loaders(cfg, "2026-11-27")
    sat = datetime(2026, 11, 14, 0, 30, tzinfo=timezone.utc)
    a = ml_paper.run(cfg, tmp_path, sat, loaders)
    assert not a["already_processed"] and a["fills"]
    expo = pd.Series(a["exposure"])
    assert abs(expo.sum()) < 1e-6                        # dollar-neutral
    assert (expo > 0).sum() == 3 and (expo < 0).sum() == 3
    assert expo.abs().sum() <= ml_paper.MAX_GROSS + 1e-6
    b = ml_paper.run(cfg, tmp_path, sat + timedelta(days=3), loaders)   # Tuesday: same week
    assert b["already_processed"] and not b["fills"]
    c = ml_paper.run(cfg, tmp_path, sat + timedelta(days=7), loaders)   # next Saturday: new week
    assert not c["already_processed"]
    sc = ml_paper.live_scorecard(tmp_path)
    assert sc["weeks_scored"] == 1                       # first week's predictions now scored
    st = ml_paper.MLState.load(tmp_path)
    assert st.weeks_traded == 2 and st.carry_earned != 0
