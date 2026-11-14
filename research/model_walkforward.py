"""Walk-forward test of the predictive model. 2008-2014 = validation, 2015-2026 = test."""
import sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, ".")
from fxbot import factors as F, model as M
from fxbot.config import load_config, pair_cost
from fxbot.data import daily_closes
from fxbot.rates import usable_rates
from fxbot.strategy import perf

cfg = load_config()
closes = pd.read_csv("data/closes_clean.csv", index_col=0, parse_dates=True)
px = F.ccy_prices(closes)
mr = pd.read_csv("data/rates_monthly.csv", index_col=0); mr.index = pd.PeriodIndex(mr.index, freq="M")
diff = F.rate_diff(usable_rates(mr), px.index, list(px.columns))
try:
    mk = pd.read_csv("data/market.csv", index_col=0, parse_dates=True)
except FileNotFoundError:
    mk = pd.DataFrame({"vix": daily_closes("^VIX", "2001-01-01"), "spx": daily_closes("^GSPC", "2001-01-01")})
    mk.to_csv("data/market.csv")
panel = M.build_panel(px, diff, mk["vix"], mk["spx"])
panel.to_pickle("data/panel.pkl")
cost = {F.CCY_OF[p]: pair_cost(cfg, p) for p in cfg["pairs"]}
rets = px.pct_change()
FIN = cfg["costs"]["financing_bps_year"]
print("panel rows", len(panel), "features", len(M.feature_cols(panel)))

def evaluate(preds, target):
    ic = M.information_coefficient(preds, target)
    w = M.positions(preds, target, px.index, list(px.columns))
    w = F.vol_target(w, rets, 0.10)
    res = F.backtest(w, px, diff, cost, FIN)
    gross = res["spot"] + res["carry"]
    out = {}
    for name, s, e in [("val 2008-14", "2008", "2014"), ("test 2015-26", "2015", None)]:
        icp = ic.loc[s:e]
        r = res.loc[s:e]
        p = perf(r["ret"], r)
        g = gross.loc[s:e]
        out[name] = {"IC": round(icp.mean(), 4), "IC_t": round(icp.mean() / icp.std() * np.sqrt(len(icp)), 2),
                     "sharpe_net": p["sharpe"], "CAGR_net%": p["CAGR_%"], "maxDD%": p["maxDD_%"],
                     "sharpe_gross": round(g.mean() / g.std() * np.sqrt(252), 2),
                     "cost%/yr": round((r["cost"] + r["financing"]).sum() / (len(r) / 252) * 100, 2)}
    return out, res

rows = []
store = {}
for target in ["y_rel", "y_abs"]:
    for kind in ["ridge", "lgbm"]:
        preds = M.walk_forward(panel, target, kind)
        store[(target, kind)] = preds
        out, res = evaluate(preds, target)
        for per, d in out.items():
            rows.append({"target": target, "model": kind, "period": per, **d})
        # luck control: shuffled labels
        for seed in (1, 2, 3):
            sp = M.walk_forward(panel, target, kind, shuffle_seed=seed * 1000)
            o, _ = evaluate(sp, target)
            for per, d in o.items():
                rows.append({"target": target, "model": f"{kind} SHUFFLED#{seed}", "period": per, **d})
        print("done", target, kind, flush=True)
df = pd.DataFrame(rows)
pd.set_option("display.width", 220)
for per in ["val 2008-14", "test 2015-26"]:
    print(f"\n== {per} ==")
    print(df[df.period == per].drop(columns="period").to_string(index=False))
df.to_csv("research/model_results.csv", index=False)
pd.to_pickle(store, "data/model_preds.pkl")
