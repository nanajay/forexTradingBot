from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from fxbot import paper
from fxbot.config import load_config


def fake_world(cfg, trend):
    idx = pd.bdate_range("2024-01-01", "2026-11-13", tz="UTC")
    rng = np.random.default_rng(2)
    base = {p: np.exp(np.cumsum(rng.normal(trend, 0.004, len(idx)))) for p in cfg["pairs"]}
    closes = pd.DataFrame(base, index=idx)
    live = {cfg["pairs"][p][0]: float(closes[p].iloc[-1]) for p in cfg["pairs"]}
    return (lambda syms, start=None, now=None: closes), (lambda sym: live[sym]), live


def test_paper_run_trades_once_per_signal_day(tmp_path):
    cfg = load_config()
    lc, lp, _ = fake_world(cfg, 0.001)
    now = datetime(2026, 11, 14, 0, 30, tzinfo=timezone.utc)
    a = paper.run_daily(cfg, tmp_path, now, lc, lp)
    assert a["fills"] and not a["already_processed"]
    assert all(f["side"] == "buy" for f in a["fills"])          # strong uptrend -> long everything
    b = paper.run_daily(cfg, tmp_path, now + timedelta(hours=1), lc, lp)
    assert b["already_processed"] and not b["fills"]
    st = paper.State.load(tmp_path)
    assert st.costs_paid > 0 and st.balance < cfg["paper"]["initial_capital"]
    gross = sum(abs(paper.notional_usd(p, st.units[p], st.mark[p])) for p in cfg["pairs"])
    assert gross / st.balance <= cfg["sizing"]["max_gross_leverage"] + 1e-6


def test_mark_to_market_usd_quote_and_usd_base():
    # long 10,000 EUR at 1.10 -> +0.01 = +$100; long 10,000 USD vs JPY at 150 -> 151 = +10,000 JPY = $66.23
    assert abs(10_000 * (1.11 - 1.10) * paper.usd_per_quote("EUR/USD", 1.11) - 100) < 1e-6
    assert abs(10_000 * (151 - 150) * paper.usd_per_quote("USD/JPY", 151) - 10_000 / 151) < 1e-6
    assert paper.notional_usd("USD/JPY", 10_000, 151) == 10_000
    assert abs(paper.notional_usd("EUR/USD", 10_000, 1.1) - 11_000) < 1e-9
