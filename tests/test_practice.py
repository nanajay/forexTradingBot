import json
from datetime import datetime, timedelta, timezone

from fxbot import practice
from fxbot.config import load_config
from fxbot.practice import DEFAULTS, plan_orders

PAIRS = ["EUR/USD", "USD/JPY"]


def px(mid, spread=0.0001, tradeable=True):
    return {"bid": mid - spread / 2, "ask": mid + spread / 2, "mid": mid, "tradeable": tradeable, "time": ""}


def test_plan_sizes_to_nav_and_handles_usd_base():
    w = {"EUR/USD": 0.5, "USD/JPY": -0.4}
    prices = {"EUR_USD": px(1.10), "USD_JPY": px(150.0, 0.01)}
    orders, skipped = plan_orders(w, {"EUR/USD": 1.10, "USD/JPY": 150.0}, 100_000, {}, prices, DEFAULTS)
    o = {x["pair"]: x for x in orders}
    assert not skipped
    assert o["EUR/USD"]["units"] == round(0.5 * 100_000 / 1.10)     # EUR units
    assert o["USD/JPY"]["units"] == -40_000                         # USD units, short


def test_plan_rails():
    marks = {"EUR/USD": 1.10, "USD/JPY": 150.0}
    # market closed
    o, s = plan_orders({"EUR/USD": 0.5, "USD/JPY": 0}, marks, 1e5, {},
                       {"EUR_USD": px(1.10, tradeable=False), "USD_JPY": px(150, 0.01)}, DEFAULTS)
    assert not o and "tradeable" in s[0]["reason"]
    # wide spread and bad price
    o, s = plan_orders({"EUR/USD": 0.5, "USD/JPY": 0.5}, marks, 1e5, {},
                       {"EUR_USD": px(1.10, spread=0.01), "USD_JPY": px(170.0, 0.01)}, DEFAULTS)
    assert not o and len(s) == 2
    # gross leverage cap
    o, s = plan_orders({"EUR/USD": 3.0, "USD/JPY": -3.0}, marks, 1e5, {},
                       {"EUR_USD": px(1.10), "USD_JPY": px(150, 0.01)}, DEFAULTS)
    assert not o and s[0]["pair"] == "*"
    # small drift is not traded, a sign flip is
    o, _ = plan_orders({"EUR/USD": 0.5, "USD/JPY": 0}, marks, 1e5, {"EUR_USD": 44_000},
                       {"EUR_USD": px(1.10), "USD_JPY": px(150, 0.01)}, DEFAULTS)
    assert not o                                                     # target 45,455 vs 44,000: <10%
    o, _ = plan_orders({"EUR/USD": -0.5, "USD/JPY": 0}, marks, 1e5, {"EUR_USD": 44_000},
                       {"EUR_USD": px(1.10), "USD_JPY": px(150, 0.01)}, DEFAULTS)
    assert o[0]["units"] == -45_455 - 44_000


class FakeOanda:
    def __init__(self, nav=100_000.0):
        self.nav, self.pos, self.orders = nav, {}, []

    def summary(self, a):
        return {"NAV": str(self.nav), "balance": str(self.nav), "unrealizedPL": "0", "financing": "0",
                "marginUsed": "0"}

    def positions(self, a):
        return dict(self.pos)

    def pricing(self, a, insts):
        return {"EUR_USD": px(1.10), "USD_JPY": px(150.0, 0.01)}

    def market_order(self, a, inst, units, tag):
        self.orders.append((inst, units))
        self.pos[inst] = self.pos.get(inst, 0) + units
        p = 1.10005 if inst == "EUR_USD" else 150.005
        return {"orderFillTransaction": {"price": str(p if units > 0 else p - 0.0001), "halfSpreadCost": "1.0"}}


def write_paper(d, now, eur_units=45_455, jpy_units=-40_000):
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json").write_text(json.dumps({
        "balance": 100_000.0, "units": {"EUR/USD": eur_units, "USD/JPY": jpy_units},
        "mark": {"EUR/USD": 1.10, "USD/JPY": 150.0}, "last_run": now.isoformat(timespec="seconds")}))


def test_run_mirrors_paper_then_is_idempotent_and_halts(tmp_path):
    cfg = load_config()
    cfg["pairs"] = {p: cfg["pairs"][p] for p in PAIRS}
    now = datetime(2026, 11, 16, 0, 30, tzinfo=timezone.utc)
    write_paper(tmp_path / "paper", now)
    fake = FakeOanda()
    out = practice.run(cfg, "trend", tmp_path / "paper", tmp_path / "out", "101-001-1", fake, now)
    assert {o[0] for o in fake.orders} == {"EUR_USD", "USD_JPY"} and not out["mismatches"]
    assert all(f["status"] == "filled" for f in out["fills"])
    again = practice.run(cfg, "trend", tmp_path / "paper", tmp_path / "out", "101-001-1", fake,
                         now + timedelta(hours=1))
    assert not again["orders"]                                       # already matches
    stale = practice.run(cfg, "trend", tmp_path / "paper", tmp_path / "out", "101-001-1", fake,
                         now + timedelta(days=3))
    assert "not updated" in stale["reason"]
    fake.nav = 40_000.0
    halted = practice.run(cfg, "trend", tmp_path / "paper", tmp_path / "out", "101-001-1", fake,
                          now + timedelta(hours=2))
    assert "HALT" in halted["reason"] and not halted["orders"]
    assert "HALTED" in practice.status(tmp_path / "out", cfg)


def test_practice_host_is_hardcoded():
    from fxbot import oanda
    assert oanda.PRACTICE_HOST == "https://api-fxpractice.oanda.com"
    src = open(oanda.__file__).read()
    assert "api-fxtrade" not in src                                  # the live host appears nowhere


def test_errors_hide_account_ids(monkeypatch):
    import pytest
    from fxbot import oanda

    class R:
        status_code = 400
        text = '{"errorMessage":"Invalid value specified for accountID"}'
    c = oanda.OandaPractice(token="x")
    monkeypatch.setattr(c.s, "request", lambda *a, **k: R())
    with pytest.raises(RuntimeError) as e:
        c.summary("101-001-5727429-001")
    assert "5727429" not in str(e.value) and "<id>" in str(e.value)


def test_gbp_account_nav_converted_to_usd(tmp_path):
    cfg = load_config()
    cfg["pairs"] = {p: cfg["pairs"][p] for p in ["EUR/USD", "GBP/USD"]}
    now = datetime(2026, 11, 16, 0, 30, tzinfo=timezone.utc)
    d = tmp_path / "paper"
    d.mkdir()
    (d / "state.json").write_text(json.dumps({
        "balance": 100_000.0, "units": {"EUR/USD": 50_000 / 1.10, "GBP/USD": 0.0},
        "mark": {"EUR/USD": 1.10, "GBP/USD": 1.30}, "last_run": now.isoformat(timespec="seconds")}))

    class GBPFake(FakeOanda):
        def summary(self, a):
            return {**super().summary(a), "currency": "GBP"}

        def pricing(self, a, insts):
            return {"EUR_USD": px(1.10), "GBP_USD": px(1.30)}
    fake = GBPFake(nav=100_000.0)                          # £100,000 = $130,000
    out = practice.run(cfg, "trend", d, tmp_path / "out", "101-004-1-001", fake, now)
    eur = [o for o in out["orders"] if o["pair"] == "EUR/USD"][0]
    assert eur["units"] == round(0.5 * 130_000 / 1.10)     # 50% of the USD value of the GBP NAV


def test_check_reports_per_endpoint_and_masks_ids():
    class F(FakeOanda):
        def accounts(self):
            return [{"id": "101-004-40999814-001"}]

        def positions(self, a):
            raise RuntimeError("OANDA GET /v3/accounts/<id>/openPositions -> 401")
    out = practice.check(F(), {"trend": "101-004-40999814-001", "ml": "101-004-40999814-002"}, ["EUR_USD"])
    assert "40999814" not in out
    assert "[trend] …814-001: listed" in out and "[ml] …814-002: NOT among" in out
    assert "positions: FAILED" in out and "summary: OK" in out
