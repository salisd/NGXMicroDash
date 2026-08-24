"""Local parquet cache.

The dashboard reads only from this cache; the fetch script is the only
component that talks to remote APIs. This keeps the app reproducible and
offline-friendly once data is fetched, and makes rate limits a one-time
cost rather than a per-pageview one.

Layout (under config.DATA_DIR):
    universe.parquet      symbol/name/sector/market table
    prices/<SYMBOL>.parquet  canonical OHLCV frame per symbol
    meta.json             fetch provenance (source, timestamps)
"""

import json
from datetime import datetime, timezone

import pandas as pd

from .. import config


def save_universe(df: pd.DataFrame) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(config.UNIVERSE_PATH, index=False)


def load_universe() -> pd.DataFrame | None:
    if not config.UNIVERSE_PATH.exists():
        return None
    return pd.read_parquet(config.UNIVERSE_PATH)


def save_prices(symbol: str, df: pd.DataFrame, source: str) -> None:
    config.PRICES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(config.PRICES_DIR / f"{symbol}.parquet")
    meta = _load_meta()
    meta["symbols"][symbol] = {
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "first_date": str(df.index.min().date()),
        "last_date": str(df.index.max().date()),
        "n_obs": int(len(df)),
        "has_high_low": bool(df["high"].notna().any() and df["low"].notna().any()),
    }
    config.META_PATH.write_text(json.dumps(meta, indent=2))


def load_prices(symbol: str) -> pd.DataFrame | None:
    path = config.PRICES_DIR / f"{symbol}.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def cached_symbols() -> list[str]:
    if not config.PRICES_DIR.exists():
        return []
    return sorted(p.stem for p in config.PRICES_DIR.glob("*.parquet"))


def _load_meta() -> dict:
    if config.META_PATH.exists():
        return json.loads(config.META_PATH.read_text())
    return {"symbols": {}}


def coverage_summary() -> pd.DataFrame:
    """One row per cached symbol: source, date range, observations, gaps."""
    meta = _load_meta()["symbols"]
    rows = []
    for sym in cached_symbols():
        df = load_prices(sym)
        m = meta.get(sym, {})
        first, last = df.index.min(), df.index.max()
        bdays = pd.bdate_range(first, last)
        rows.append(
            {
                "symbol": sym,
                "source": m.get("source", "?"),
                "first_date": first.date(),
                "last_date": last.date(),
                "n_obs": len(df),
                "n_business_days": len(bdays),
                "missing_days": len(bdays) - len(df),
                "zero_volume_days": int((df["volume"] == 0).sum()),
                "has_high_low": bool(df["high"].notna().any()),
            }
        )
    return pd.DataFrame(rows)
