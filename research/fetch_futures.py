"""Download front-month CME FX futures (Yahoo) next to spot, for implied carry research."""
import pandas as pd
from fxbot.data import daily_closes
FUT = {"EUR/USD": "6E=F", "GBP/USD": "6B=F", "USD/JPY": "6J=F", "AUD/USD": "6A=F",
       "USD/CAD": "6C=F", "USD/CHF": "6S=F", "NZD/USD": "6N=F"}
df = pd.DataFrame({p: daily_closes(s, "2001-01-01") for p, s in FUT.items()})
df.to_csv("data/futures.csv")
print(df.tail(3)); print(df.notna().sum())
