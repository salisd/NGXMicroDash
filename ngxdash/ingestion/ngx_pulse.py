"""NGX Pulse (https://ngxpulse.ng/api) historical price source.

Personal (free) keys are documented for 'stock prices and market overview';
'Historical data' is listed as a Professional-tier feature, but the
/prices/:symbol endpoint documents from/to/days parameters ('Full history
runs from January 2017') without a tier badge. This client therefore tries
the historical query and raises SourceDataError with a clear message if the
key's tier only yields a snapshot — it never fabricates a series from one.

Rate limits (Personal): 10 req/min, 100 req/day -> caller should pass
inter_request_sleep >= 6.5s and fetch incrementally.
"""

import requests
import pandas as pd

from .base import SourceDataError, normalize_ohlcv

BASE_URL = "https://www.ngxpulse.ng"


class NGXPulseSource:
    name = "ngx_pulse"

    def __init__(self, api_key: str, timeout: int = 30):
        if not api_key:
            raise ValueError("NGX_PULSE_API_KEY is not set")
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = api_key
        self.timeout = timeout

    def _get(self, path: str, **params):
        resp = self.session.get(BASE_URL + path, params=params, timeout=self.timeout)
        if resp.status_code == 429:
            raise SourceDataError("ngx_pulse: rate limited (429) — slow down or retry tomorrow")
        resp.raise_for_status()
        return resp.json()

    def fetch_history(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        params = {}
        if start:
            params["from"] = start
        if end:
            params["to"] = end
        payload = self._get(f"/api/ngxdata/prices/{symbol}", **params)

        # The historical response shape is not documented; accept either a
        # bare list of daily records or a wrapper dict containing one.
        records = None
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            for key in ("history", "prices", "data", "results"):
                if isinstance(payload.get(key), list):
                    records = payload[key]
                    break
            if records is None:
                raise SourceDataError(
                    f"ngx_pulse: {symbol} returned a single snapshot "
                    f"(keys: {sorted(payload.keys())}). Historical data is "
                    "likely not enabled for this API key tier."
                )
        if records is None:
            raise SourceDataError(f"ngx_pulse: unexpected payload type for {symbol}")
        df = normalize_ohlcv(records, self.name, symbol)
        # Verified empirically (2026-08): historical rows from this API carry
        # close+volume only — "open" is the close duplicated, and high/low
        # exist solely on the current-day snapshot row. Store what the
        # source genuinely provides rather than a fabricated-looking OHLC.
        df[["open", "high", "low"]] = float("nan")
        return df
