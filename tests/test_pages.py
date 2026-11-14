import json
from datetime import datetime, timezone

import pandas as pd

from fxbot import pages
from fxbot.config import load_config


def setup(root):
    p = root / "paper"
    p.mkdir()
    (p / "state.json").write_text(json.dumps({
        "started": "2026-11-16T00:30:00+00:00", "initial_capital": 10_000.0, "balance": 10_100.0,
        "costs_paid": 5.0, "units": {"EUR/USD": -6000.0, "USD/JPY": 3000.0},
        "mark": {"EUR/USD": 1.10, "USD/JPY": 150.0}}))
    pd.DataFrame({"time": ["2026-11-16T00:30:00+00:00", "2026-11-17T00:30:00+00:00"],
                  "equity": [10_000.0, 10_100.0]}).to_csv(p / "equity.csv", index=False)
    pd.DataFrame({"time": ["2026-11-17T00:30:00+00:00"], "pair": ["EUR/USD"], "side": ["sell"],
                  "units": [6000]}).to_csv(p / "fills.csv", index=False)
    q = root / "practice_trend"
    q.mkdir()
    (q / "state.json").write_text(json.dumps({"started": "2026-11-16T00:31:00+00:00", "start_nav": 100_000.0,
                                              "currency": "GBP", "halted": False}))
    pd.DataFrame({"time": ["2026-11-16T00:31:00+00:00", "2026-11-17T00:31:00+00:00"],
                  "nav": [100_000.0, 100_800.0], "financing_total": [0, 0], "gross_leverage": [1, 1]}
                 ).to_csv(q / "equity.csv", index=False)
    pd.DataFrame({"time": ["2026-11-17T00:31:00+00:00"], "pair": ["EUR/USD"], "units": [-6000],
                  "status": ["filled"], "price": [1.1], "slippage_vs_mid_bps": [0.5]}
                 ).to_csv(q / "fills.csv", index=False)


def test_pages(tmp_path):
    setup(tmp_path)
    now = datetime(2026, 11, 17, 0, 45, tzinfo=timezone.utc)
    overview = pages.write_all(load_config(), tmp_path, now)
    trend = (tmp_path / "paper" / "REPORT.md").read_text()
    ml = (tmp_path / "paper_ml" / "REPORT.md").read_text()
    assert "| **Account value** | **$10,100.00** | **£100,800.00** |" in trend
    assert "🟢 +$100.00 (+1.00%)" in trend and "🟢 +£800.00 (+0.80%)" in trend
    assert "| EUR | ↓ falls | 0.65× |" in trend and "| JPY | ↓ falls | 0.30× |" in trend
    assert "the same trades, filled at OANDA ✅" in trend
    assert (tmp_path / "paper" / "report_equity.svg").exists() and "report_equity.svg" in trend
    assert "Go-live check" in trend and "Long enough on OANDA practice" in trend
    assert "not started" in ml                                   # learning model has no data here
    assert "[📈 Forex trend strategy](paper/REPORT.md)" in overview
    assert "sold EUR/USD · OANDA: same, filled ✅" in overview
    assert (tmp_path / "REPORT.md").exists()


def test_svg_handles_single_point_and_lines():
    one = pages.svg_lines({"Paper": pd.Series([-0.05], index=["2026-11-14"])}, "t")
    assert "<circle" in one and "0%" in one
    many = pages.svg_lines({"Paper": pd.Series([0.0, 0.5, -0.3], index=["a", "b", "c"])}, "t")
    assert "<polyline" in many
