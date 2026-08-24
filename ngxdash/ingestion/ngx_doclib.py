"""Universe and sector classification from NGX's own public doclib REST API.

https://doclib.ngxgroup.com/REST/api/statistics/equities/ returns the current
day's equity board with the exchange's official sector classification. It is
public (no key) and is the authoritative source for symbol -> sector mapping,
regardless of which vendor supplies price history.
"""

import requests
import pandas as pd

DOCLIB_URL = (
    "https://doclib.ngxgroup.com/REST/api/statistics/equities/"
    "?market=&sector=&orderby=&pageSize=400&pageNo=0"
)


def fetch_universe(timeout: int = 30) -> pd.DataFrame:
    """Return DataFrame[symbol, name, sector, market, value_traded].

    value_traded is the day's naira turnover — used to rank symbols by
    trading activity when selecting the fetch universe.
    """
    resp = requests.get(DOCLIB_URL, headers={"Accept": "application/json"}, timeout=timeout)
    resp.raise_for_status()
    rows = resp.json()
    df = pd.DataFrame(
        {
            "symbol": [r["Symbol"].strip() for r in rows],
            "name": [(r.get("Company2") or r["Symbol"]).strip() for r in rows],
            "sector": [(r.get("Sector") or "UNCLASSIFIED").strip().upper() for r in rows],
            "market": [(r.get("Market") or "").strip() for r in rows],
            "value_traded": [float(r.get("Value") or 0.0) for r in rows],
        }
    )
    return df.drop_duplicates("symbol").reset_index(drop=True)


def select_universe(
    universe: pd.DataFrame,
    sectors: list[str],
    per_sector: int = 6,
) -> pd.DataFrame:
    """Top `per_sector` symbols by traded value within each requested sector."""
    subset = universe[universe["sector"].isin(sectors)]
    return (
        subset.sort_values("value_traded", ascending=False)
        .groupby("sector", group_keys=False)
        .head(per_sector)
        .sort_values(["sector", "value_traded"], ascending=[True, False])
        .reset_index(drop=True)
    )
