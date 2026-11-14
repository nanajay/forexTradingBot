"""Short-term interest rates per currency from FRED (public CSV, no API key).

Main source: OECD 3-month interbank rates (monthly). Where an OECD series stops early
(the euro area and UK series end in Jan 2026), it's extended with the monthly average
of the daily overnight rate (euro: ESTR, sterling: SONIA).

No lookahead: a monthly value for month M is only used from the first day of month M+2,
since FRED publishes these with a delay of a few weeks.
"""
from __future__ import annotations

import io
import time

import pandas as pd
import requests

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"
OECD = {"USD": "IR3TIB01USM156N", "EUR": "IR3TIB01EZM156N", "GBP": "IR3TIB01GBM156N",
        "JPY": "IR3TIB01JPM156N", "AUD": "IR3TIB01AUM156N", "CAD": "IR3TIB01CAM156N",
        "CHF": "IR3TIB01CHM156N", "NZD": "IR3TIB01NZM156N"}
OVERNIGHT = {"EUR": "ECBESTRVOLWGTTRMDMNRT", "GBP": "IUDSOIA"}
PUBLICATION_LAG_MONTHS = 2


def _fred(series_id: str, retries: int = 4) -> pd.Series:
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(URL.format(id=series_id), timeout=30,
                             headers={"User-Agent": "fx-trend-bot"})
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
            s.index = pd.to_datetime(df.iloc[:, 0])
            return s.dropna()
        except Exception as e:
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"FRED {series_id} failed: {last}")


def monthly_rates(fetch=_fred) -> pd.DataFrame:
    """Monthly rate (%) per currency, indexed by the month it describes."""
    cols = {}
    for ccy, sid in OECD.items():
        s = fetch(sid)
        s.index = s.index.to_period("M")
        if ccy in OVERNIGHT:
            o = fetch(OVERNIGHT[ccy])
            o = o.groupby(o.index.to_period("M")).mean()
            s = pd.concat([s, o[o.index > s.index.max()]])
        cols[ccy] = s
    return pd.DataFrame(cols).sort_index()


def usable_rates(monthly: pd.DataFrame) -> pd.DataFrame:
    """Shift to the date each value can actually be known (first day of M + lag), UTC daily index."""
    idx = (monthly.index + PUBLICATION_LAG_MONTHS).to_timestamp().tz_localize("UTC")
    return pd.DataFrame(monthly.to_numpy(), index=idx, columns=monthly.columns)
