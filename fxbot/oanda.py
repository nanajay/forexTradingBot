"""Minimal OANDA v20 REST client, PRACTICE (demo) accounts ONLY.

The practice host is hard-coded and there is no setting or flag that points it anywhere else:
this module cannot reach a real-money OANDA account. Even a live-account token would be rejected
by the practice server.

Credentials come from environment variables (GitHub secrets), never from files:
    OANDA_API_TOKEN      personal access token for the practice account
    OANDA_ACCOUNT_TREND  practice (sub-)account id the trend strategy trades
    OANDA_ACCOUNT_ML     practice (sub-)account id the learning model trades
"""
from __future__ import annotations

import os
import time
import uuid

import requests

PRACTICE_HOST = "https://api-fxpractice.oanda.com"


def instrument(pair: str) -> str:
    return pair.replace("/", "_")                       # "EUR/USD" -> "EUR_USD"


class OandaPractice:
    def __init__(self, token: str | None = None, timeout: int = 20):
        self.token = token or os.environ.get("OANDA_API_TOKEN", "")
        if not self.token:
            raise RuntimeError("OANDA_API_TOKEN is not set")
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {self.token}",
                               "Content-Type": "application/json",
                               "Accept-Datetime-Format": "RFC3339"})

    def _req(self, method: str, path: str, retries: int = 3, **kw) -> dict:
        url = PRACTICE_HOST + path
        assert url.startswith(PRACTICE_HOST + "/v3/")     # never anything but the practice API
        last = None
        for attempt in range(retries):
            try:
                r = self.s.request(method, url, timeout=self.timeout, **kw)
            except requests.RequestException as e:          # network error: safe to retry reads
                last = e
                if method != "GET":
                    raise
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 500 and method == "GET":
                last = RuntimeError(f"{r.status_code} {r.text[:200]}")
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"OANDA {method} {path} -> {r.status_code}: {r.text[:300]}")
            return r.json()
        raise RuntimeError(f"OANDA {method} {path} failed: {last}")

    # ---- reads -------------------------------------------------------------------------
    def accounts(self) -> list[dict]:
        return self._req("GET", "/v3/accounts")["accounts"]

    def summary(self, account: str) -> dict:
        return self._req("GET", f"/v3/accounts/{account}/summary")["account"]

    def positions(self, account: str) -> dict[str, float]:
        """Net units per instrument (long minus short)."""
        out = {}
        for p in self._req("GET", f"/v3/accounts/{account}/openPositions")["positions"]:
            out[p["instrument"]] = float(p["long"]["units"]) + float(p["short"]["units"])
        return out

    def pricing(self, account: str, instruments: list[str]) -> dict[str, dict]:
        data = self._req("GET", f"/v3/accounts/{account}/pricing",
                         params={"instruments": ",".join(instruments)})
        out = {}
        for p in data["prices"]:
            bid, ask = float(p["bids"][0]["price"]), float(p["asks"][0]["price"])
            out[p["instrument"]] = {"bid": bid, "ask": ask, "mid": (bid + ask) / 2,
                                    "tradeable": bool(p.get("tradeable", False)), "time": p["time"]}
        return out

    # ---- orders ------------------------------------------------------------------------
    def market_order(self, account: str, inst: str, units: int, tag: str) -> dict:
        """Fill-or-kill market order. Positive units buy, negative sell. Never retried
        automatically (a retry after a timeout could double the order)."""
        body = {"order": {"type": "MARKET", "instrument": inst, "units": str(int(units)),
                          "timeInForce": "FOK", "positionFill": "DEFAULT",
                          "clientExtensions": {"id": f"fxbot-{uuid.uuid4().hex[:12]}", "tag": tag[:50]}}}
        return self._req("POST", f"/v3/accounts/{account}/orders", retries=1, json=body)
