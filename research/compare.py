"""Candidate comparison. Selection uses 2004-2014 ONLY; 2015+ is out-of-sample."""
import sys
import pandas as pd
sys.path.insert(0, ".")
from fxbot import factors as F
from fxbot.config import load_config, pair_cost
from fxbot.rates import monthly_rates, usable_rates
from fxbot.strategy import perf

cfg = load_config()
closes = pd.read_csv("data/closes_clean.csv", index_col=0, parse_dates=True)
px = F.ccy_prices(closes)
mr = monthly_rates(); mr.to_csv("data/rates_monthly.csv")
diff = F.rate_diff(usable_rates(mr), px.index, list(px.columns))
cost = {F.CCY_OF[p]: pair_cost(cfg, p) for p in cfg["pairs"]}
rets = px.pct_change()
FIN = cfg["costs"]["financing_bps_year"]

raw = {
    "trend (crypto rules)": F.sleeve_trend(px),
    "carry": F.sleeve_carry(diff),
    "momentum 12m": F.sleeve_momentum(px),
    "value (5y reversal)": F.sleeve_value(px),
}
sleeves = {k: F.vol_target(v, rets, 0.10) for k, v in raw.items()}
def combo(names):
    parts = [sleeves[n] for n in names]
    return F.vol_target(sum(parts) / len(parts), rets, 0.10)
sleeves["combo carry+trend+value"] = combo(["carry", "trend (crypto rules)", "value (5y reversal)"])
sleeves["combo carry+value"] = combo(["carry", "value (5y reversal)"])
sleeves["combo all four"] = combo(["carry", "trend (crypto rules)", "value (5y reversal)", "momentum 12m"])

periods = [("IS 2004-2014", "2004-01-01", "2014-12-31"), ("OOS 2015-2026", "2015-01-01", None)]
rows = []
for name, e in sleeves.items():
    res = F.backtest(e, px, diff, cost, FIN)
    for pname, s, en in periods:
        r = res.loc[s:en]
        p = perf(r["ret"], r)
        yrs = len(r) / 252
        rows.append({"strategy": name, "period": pname, "CAGR%": p["CAGR_%"], "sharpe": p["sharpe"],
                     "maxDD%": p["maxDD_%"], "vol%": p["vol_%"], "worst_yr%": p["worst_year_%"],
                     "carry%/yr": round(r["carry"].sum() / yrs * 100, 2),
                     "cost%/yr": round((r["cost"] + r["financing"]).sum() / yrs * 100, 2),
                     "lev": p["avg_gross_lev"]})
    res.to_csv(f"data/res_{name.split()[0]}_{len(name)}.csv")
df = pd.DataFrame(rows)
pd.set_option("display.width", 200)
for pname, _, _ in periods:
    print(f"\n== {pname} ==")
    print(df[df.period == pname].drop(columns="period").to_string(index=False))
corr = pd.DataFrame({k: F.backtest(v, px, diff, cost, FIN)["ret"] for k, v in sleeves.items() if "combo" not in k})
print("\ncorrelation IS:\n", corr.loc[:"2014"].corr().round(2))
