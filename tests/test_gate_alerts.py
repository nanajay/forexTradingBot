import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from fxbot import alerts, gate
from fxbot.config import load_config


def build(root, weeks=27, nav_end=101_000.0, slip=0.8, fin=-200.0, missed=0, mismatch=False,
          paper_ret=0.008, preds=None):
    start = pd.Timestamp("2026-11-16 00:30", tz="UTC")
    days = pd.bdate_range(start, periods=weeks * 5, tz="UTC")
    days = days[missed:] if missed else days
    for s in ("trend", "ml"):
        d = root / f"practice_{s}"
        d.mkdir(parents=True)
        (d / "state.json").write_text(json.dumps({"started": start.isoformat(), "start_nav": 100_000.0,
                                                  "halted": False, "currency": "GBP"}))
        nav = np.linspace(100_000, nav_end, len(days))
        pd.DataFrame({"time": [t.isoformat() for t in days], "nav": nav, "financing_total": fin,
                      "gross_leverage": 2.0}).to_csv(d / "equity.csv", index=False)
        pd.DataFrame({"time": [days[0].isoformat()] * 4, "pair": ["EUR/USD"] * 4, "status": ["filled"] * 4,
                      "slippage_vs_mid_bps": [slip] * 4}).to_csv(d / "fills.csv", index=False)
        (d / "RUNS.md").write_text("- ok\n" + ("- x MISMATCH: [..]\n" if mismatch else ""))
    for pdir in ("paper", "paper_ml"):
        p = root / pdir
        p.mkdir()
        pd.DataFrame({"time": [days[0].isoformat(), days[-1].isoformat()],
                      "equity": [10_000, 10_000 * (1 + paper_ret)]}).to_csv(p / "equity.csv", index=False)
    if preds is not None:
        preds.to_csv(root / "paper_ml" / "predictions.csv", index=False)
    return days[-1].to_pydatetime()


def by_name(checks):
    return {c.name: c for c in gate.evaluate(load_config(), *checks)}


def test_trend_ready_when_everything_passes(tmp_path):
    now = build(tmp_path)
    c = gate.evaluate(load_config(), tmp_path, "trend", now)
    assert gate.verdict(c) == "READY", [(x.name, x.status, x.detail) for x in c]


def test_waits_before_26_weeks_and_fails_on_problems(tmp_path):
    now = build(tmp_path / "a", weeks=8, fin=-50.0)
    c = {x.name: x for x in gate.evaluate(load_config(), tmp_path / "a", "trend", now)}
    assert c["duration"].status == "WAIT" and c["edge"].status == "WAIT"
    assert gate.verdict(list(c.values())) == "WAIT"
    now = build(tmp_path / "b", nav_end=97_000.0, slip=3.0, missed=6, mismatch=True, paper_ret=0.02)
    c = {x.name: x for x in gate.evaluate(load_config(), tmp_path / "b", "trend", now)}
    for name in ("edge", "costs", "agreement", "reliability"):
        assert c[name].status == "FAIL", name
    assert gate.verdict(list(c.values())) == "NOT READY"


def test_ml_needs_significant_live_ic(tmp_path):
    rng = np.random.default_rng(0)
    rows = []
    for w in range(27):
        real = rng.normal(size=7)
        for i in range(7):
            rows.append({"signal_day": f"w{w:02d}", "ccy": i, "pred": rng.normal(), "realized": real[i]})
    now = build(tmp_path, preds=pd.DataFrame(rows))              # random predictions: no edge
    c = {x.name: x for x in gate.evaluate(load_config(), tmp_path, "ml", now)}
    assert c["edge"].status == "FAIL" and "live IC" in c["edge"].detail


def test_no_practice_data_waits(tmp_path):
    c = gate.evaluate(load_config(), tmp_path, "trend")
    assert gate.verdict(c) == "WAIT"


def test_gate_change_flag(tmp_path):
    cfg = load_config()
    gate.report(cfg, tmp_path)                                 # first run: records only
    assert not (tmp_path / "results" / ".gate_changed").exists()
    build(tmp_path)
    gate.report(cfg, tmp_path)
    assert (tmp_path / "results" / ".gate_changed").exists()


def test_alerts(tmp_path):
    import os
    sent = []
    post = lambda url, **kw: sent.append((url, kw))
    tue = datetime(2026, 11, 17, 0, 40, tzinfo=timezone.utc)
    (tmp_path / "results").mkdir()
    # quiet day: a daily summary is still printed (nothing configured -> nothing sent)
    r = alerts.run(tmp_path, {"paper": "success"}, tue, post)
    assert r["sent"] == [] and "daily summary" in r["message"] and "not started" in r["body"]
    os.environ["ALERT_NTFY_TOPIC"] = "t-test"
    os.environ["ALERT_WEBHOOK_URL"] = "https://example.invalid/hook"
    try:
        # failed step -> PROBLEM title, high priority, both channels
        r = alerts.run(tmp_path, {"paper": "success", "ml": "failure"}, tue, post)
        assert r["sent"] == ["ntfy", "webhook"] and "problem" in r["message"] and "⚠️ PROBLEMS" in r["body"]
        assert sent[0][0] == "https://ntfy.sh/t-test" and sent[0][1]["headers"]["Priority"] == "high"
        # mismatch in today's practice run is reported
        d = tmp_path / "practice_trend"
        d.mkdir()
        (d / "RUNS.md").write_text("- 2026-11-17T00:31:00 [trend] ... MISMATCH: [{'pair': 'EUR/USD'}]\n")
        r = alerts.run(tmp_path, {}, tue, post)
        assert any("MISMATCH" in p for p in r["problems"])
        # an alert failure never raises
        def boom(*a, **k):
            raise OSError("network down")
        assert alerts.run(tmp_path, {"ml": "failure"}, tue, boom)["sent"][0].startswith("failed")
    finally:
        del os.environ["ALERT_NTFY_TOPIC"], os.environ["ALERT_WEBHOOK_URL"]


def test_daily_summary_shows_trades_day_change_and_total(tmp_path):
    import pandas as pd
    p = tmp_path / "paper"
    p.mkdir()
    (p / "state.json").write_text(json.dumps({"initial_capital": 10_000.0,
                                              "units": {"EUR/USD": 1234.5, "USD/JPY": 500.0}}))
    pd.DataFrame({"time": ["2026-11-16T00:30:00+00:00", "2026-11-17T00:30:00+00:00"],
                  "equity": [10_000.0, 10_100.0]}).to_csv(p / "equity.csv", index=False)
    pd.DataFrame({"time": ["2026-11-17T00:30:00+00:00"], "pair": ["EUR/USD"], "side": ["buy"],
                  "units": [1234.5]}).to_csv(p / "fills.csv", index=False)
    q = tmp_path / "practice_trend"
    q.mkdir()
    (q / "state.json").write_text(json.dumps({"start_nav": 100_000.0, "currency": "GBP"}))
    pd.DataFrame({"time": ["2026-11-16T00:31:00+00:00", "2026-11-17T00:31:00+00:00"],
                  "nav": [100_000.0, 99_500.0]}).to_csv(q / "equity.csv", index=False)
    pd.DataFrame({"time": ["2026-11-17T00:31:00+00:00"] * 2, "pair": ["EUR/USD", "USD/JPY"],
                  "units": [5000, -3000], "status": ["filled", "rejected"], "price": [1.1, 150.0]}
                 ).to_csv(q / "fills.csv", index=False)
    now = datetime(2026, 11, 17, 0, 40, tzinfo=timezone.utc)
    text = "\n".join(alerts.daily_summary(tmp_path, now))
    assert "Paper (simulated): $10,100.00" in text and "🟢 +$100.00 today (+1.00%) · total +1.00%" in text
    assert "OANDA practice: £99,500.00" in text and "🔴 −£500.00 today (−0.50%) · total −0.50%" in text
    assert "Trades today: bought EUR/USD" in text
    assert "Practice: same trades filled at OANDA ✅" in text          # the rejected USD/JPY isn't a trade
    assert "Holding: ↑ EUR · ↓ JPY (vs USD)" in text                   # long USD/JPY = short JPY
    assert "🤖 LEARNING MODEL" in text and "not started yet" in text
    assert "GO-LIVE CHECK" in text
    r = alerts.run(tmp_path, {"paper": "success"}, now, lambda *a, **k: None)
    assert "1 problem(s)" in r["message"] and "rejected" in r["body"]     # the rejected order is flagged
    (q / "fills.csv").write_text("time,pair,units,status,price\n")       # without it: a normal headline
    r = alerts.run(tmp_path, {"paper": "success"}, now, lambda *a, **k: None)
    assert "up 0.25% today" in r["message"]                              # avg of +1.00% and −0.50%
