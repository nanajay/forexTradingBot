import sys, warnings; warnings.filterwarnings("ignore")
import pandas as pd, numpy as np
sys.path.insert(0, ".")
from fxbot import factors as F
from fxbot.config import load_config, pair_cost
from fxbot.rates import usable_rates
cfg = load_config()
closes = pd.read_csv("data/closes_clean.csv", index_col=0, parse_dates=True)
px = F.ccy_prices(closes); rets = px.pct_change()
mr = pd.read_csv("data/rates_monthly.csv", index_col=0); mr.index = pd.PeriodIndex(mr.index, freq="M")
diff = F.rate_diff(usable_rates(mr), px.index, list(px.columns))
cost = {F.CCY_OF[p]: pair_cost(cfg, p) for p in cfg["pairs"]}
raw = {"trend": F.sleeve_trend(px), "carry": F.sleeve_carry(diff), "mom": F.sleeve_momentum(px), "value": F.sleeve_value(px)}
def sh(x): return round(x.mean()/x.std()*np.sqrt(252),2)
print("gross Sharpe (spot+carry, no costs, no financing), unscaled sleeves:")
for k,v in raw.items():
    r = F.backtest(v, px, diff, {c:0 for c in cost}, 0)
    out=[k]
    for s,e in [("2004","2014"),("2015",None),("2019",None)]:
        rr=r.loc[s:e]; out += [sh(rr.ret), round(rr.spot.mean()*252*100,2), round(rr.carry.mean()*252*100,2)]
    print(out)
# by year carry sleeve
r = F.backtest(raw["carry"], px, diff, {c:0 for c in cost}, 0)
print("carry sleeve yearly gross %:", ((1+r.ret).groupby(r.index.year).prod()-1).mul(100).round(1).to_dict())
r = F.backtest(raw["trend"], px, diff, {c:0 for c in cost}, 0)
print("trend sleeve yearly gross %:", ((1+r.ret).groupby(r.index.year).prod()-1).mul(100).round(1).to_dict())
