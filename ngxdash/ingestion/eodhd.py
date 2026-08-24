"""EODHD (https://eodhd.com) historical price source for NGX (exchange XNSA).

Free tier: 20 API calls/day; paid All-World plan lifts limits and history
depth. Responses are documented JSON:
[{date, open, high, low, close, adjusted_close, volume}, ...]
"""

import requests
import pandas as pd

from .base import SourceDataError, normalize_ohlcv

BASE_URL = "https://eodhd.com/api"


class EODHDSource:
    name = "eodhd"

    def __init__(self, api_token: str, timeout: int = 30):
        if not api_token:
            raise ValueError("EODHD_API_TOKEN is not set")
        self.token = api_token
        self.timeout = timeout

    def fetch_history(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        params = {"api_token": self.token, "fmt": "json", "period": "d"}
        if start:
            params["from"] = start
        if end:
            params["to"] = end
        resp = requests.get(
            f"{BASE_URL}/eod/{symbol}.XNSA", params=params, timeout=self.timeout
        )
        if resp.status_code == 402:
            raise SourceDataError("eodhd: payment required — plan does not cover this request")
        if resp.status_code == 429:
            raise SourceDataError("eodhd: rate limited (429) — free tier is 20 calls/day")
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, list):
            raise SourceDataError(f"eodhd: unexpected payload for {symbol}: {payload!r:.200}")
        # Prefer raw close over adjusted_close: microstructure estimators
        # need traded prices, and NGX corporate actions would otherwise
        # contaminate high/low vs close consistency.
        for rec in payload:
            rec.pop("adjusted_close", None)
        return normalize_ohlcv(payload, self.name, symbol)
