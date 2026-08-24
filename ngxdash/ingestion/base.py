"""Shared ingestion schema and normalization.

Every source is normalized to a DataFrame indexed by trading date with
columns OHLCV_COLUMNS. Columns a source genuinely does not provide are
present but all-NaN — downstream analytics check availability explicitly
(e.g. Corwin-Schultz needs high/low) instead of silently fabricating values.
"""

import numpy as np
import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]

# Field-name candidates seen across NGX-adjacent APIs, in priority order.
_FIELD_ALIASES = {
    "date": ["date", "trade_date", "tradedate", "Date", "TradeDate", "timestamp"],
    "open": ["open", "opening_price", "OpeningPrice", "open_price"],
    "high": ["high", "high_price", "HighPrice"],
    "low": ["low", "low_price", "LowPrice"],
    "close": ["close", "close_price", "ClosePrice", "closing_price",
              "current_price", "price", "adjusted_close"],
    "volume": ["volume", "Volume", "traded_volume"],
}


class SourceDataError(RuntimeError):
    """A data source responded, but not with usable historical OHLCV."""


def normalize_ohlcv(records: list[dict], source: str, symbol: str) -> pd.DataFrame:
    """Map a list of raw records onto the canonical OHLCV frame.

    Raises SourceDataError when no date field or no close field can be
    found, or when fewer than 2 dated rows come back — the signatures of a
    snapshot-only (tier-limited) response rather than a history.
    """
    if not records:
        raise SourceDataError(f"{source}: empty response for {symbol}")
    keys = records[0].keys()

    def pick(field: str) -> str | None:
        return next((a for a in _FIELD_ALIASES[field] if a in keys), None)

    date_key = pick("date")
    close_key = pick("close")
    if date_key is None or close_key is None:
        raise SourceDataError(
            f"{source}: response for {symbol} has no date/close fields "
            f"(keys: {sorted(keys)}). This usually means the API returned a "
            "latest-price snapshot instead of history — check your key's tier."
        )

    df = pd.DataFrame.from_records(records)
    out = pd.DataFrame(index=pd.to_datetime(df[date_key]).dt.normalize())
    out.index.name = "date"
    for field in OHLCV_COLUMNS:
        key = pick(field)
        values = pd.to_numeric(df[key], errors="coerce").to_numpy() if key else np.nan
        out[field] = pd.Series(values, index=out.index, dtype="float64")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["close"])
    if len(out) < 2:
        raise SourceDataError(
            f"{source}: only {len(out)} dated observation(s) for {symbol} — "
            "not a usable history."
        )
    out.attrs["source"] = source
    out.attrs["symbol"] = symbol
    return out
