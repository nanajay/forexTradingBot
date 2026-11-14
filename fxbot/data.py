"""Daily FX closes from Yahoo Finance's public chart API (no API key).

Only CLOSED trading days are returned: weekend quotes and the bar for the current
(still forming) UTC day are dropped, so signals never see a partial day.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

log = logging.getLogger("data")

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (fx-trend-bot)"}


def _get(symbol: str, params: dict, retries: int = 4) -> dict:
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(URL.format(symbol=symbol), params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            res = r.json()["chart"]["result"]
            if not res:
                raise ValueError(f"no data for {symbol}")
            return res[0]
        except Exception as e:  # network hiccup or rate limit: back off and retry
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Yahoo request for {symbol} failed: {last}")


def parse_chart(res: dict) -> pd.Series:
    ts = res.get("timestamp") or []
    closes = res["indicators"]["quote"][0]["close"]
    s = pd.Series(closes, index=pd.to_datetime(ts, unit="s", utc=True), dtype=float)
    s.index = s.index.normalize()                       # bar date (UTC)
    s = s.dropna()
    s = s[~s.index.duplicated(keep="last")]
    return s.sort_index()


def closed_only(s: pd.Series, now: datetime | None = None) -> pd.Series:
    now = now or datetime.now(timezone.utc)
    today = pd.Timestamp(now).normalize()
    s = s[s.index < today]                              # today's bar is still forming
    s = s[s.index.dayofweek < 5]                        # drop weekend quotes
    return s[s > 0]


def daily_closes(symbol: str, start: str = "2003-01-01", now: datetime | None = None) -> pd.Series:
    now = now or datetime.now(timezone.utc)
    p1 = int(pd.Timestamp(start, tz="UTC").timestamp())
    res = _get(symbol, {"period1": p1, "period2": int(now.timestamp()) + 86_400,
                        "interval": "1d", "events": "history"})
    return closed_only(parse_chart(res), now)


def latest_price(symbol: str) -> float:
    """Most recent quote (used as the mid price for simulated fills)."""
    res = _get(symbol, {"range": "1d", "interval": "5m"})
    px = res["meta"].get("regularMarketPrice")
    if not px:
        raise RuntimeError(f"no live price for {symbol}")
    return float(px)


def clean_spikes(s: pd.Series, jump: float = 0.03, back: float = 0.01) -> pd.Series:
    """Remove one-day bad ticks: a close more than `jump` away from the day before
    that comes back to within `back` of it the next day. Genuine shocks (the 2015 CHF
    de-peg, Brexit) do not revert, so they are kept. The latest close can't be checked yet."""
    lr = np.log(s)
    out_move = (lr - lr.shift(1)).abs()
    round_trip = (lr.shift(-1) - lr.shift(1)).abs()
    bad = (out_move > jump) & (round_trip < back)
    return s.mask(bad).ffill()


def load_closes(symbols: dict[str, str], start: str = "2003-01-01",
                now: datetime | None = None) -> pd.DataFrame:
    """{pair: yahoo_symbol} -> DataFrame of closes, one column per pair, aligned on
    trading days. Small holes (a holiday on one feed) are forward-filled up to 3 days."""
    cols = {p: clean_spikes(daily_closes(sym, start, now)) for p, sym in symbols.items()}
    df = pd.DataFrame(cols).sort_index()
    return df.ffill(limit=3)
