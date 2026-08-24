"""Sector-level aggregation of per-security metrics.

Choices (documented, deliberate):
* Spreads: cross-sectional MEDIAN across constituents per date — robust to
  the extreme estimates thin names produce.
* Realized vol: cross-sectional median per date ("typical constituent
  volatility"), consistent with the spread aggregation. This is *not* the
  volatility of a sector portfolio (which would be lower via
  diversification); the dashboard labels it accordingly.
* Volume: SUM across constituents — sector turnover is naturally additive.

A sector value is only reported on dates with at least `min_constituents`
members observed, so a sector line never quietly degenerates into one stock.
"""

import pandas as pd


def _panel(per_symbol: dict[str, pd.Series]) -> pd.DataFrame:
    return pd.DataFrame(per_symbol).sort_index()


def sector_median(
    per_symbol: dict[str, pd.Series],
    sector_of: dict[str, str],
    min_constituents: int = 3,
) -> pd.DataFrame:
    """Cross-sectional median per sector per date."""
    panel = _panel(per_symbol)
    out = {}
    for sector in sorted(set(sector_of.get(s) for s in panel.columns) - {None}):
        cols = [s for s in panel.columns if sector_of.get(s) == sector]
        block = panel[cols]
        med = block.median(axis=1)
        med[block.notna().sum(axis=1) < min_constituents] = pd.NA
        out[sector] = med.astype("float64")
    return pd.DataFrame(out)


def sector_sum(
    per_symbol: dict[str, pd.Series],
    sector_of: dict[str, str],
    min_constituents: int = 1,
) -> pd.DataFrame:
    """Cross-sectional sum per sector per date (for volume)."""
    panel = _panel(per_symbol)
    out = {}
    for sector in sorted(set(sector_of.get(s) for s in panel.columns) - {None}):
        cols = [s for s in panel.columns if sector_of.get(s) == sector]
        block = panel[cols]
        total = block.sum(axis=1, min_count=1)
        total[block.notna().sum(axis=1) < min_constituents] = pd.NA
        out[sector] = total.astype("float64")
    return pd.DataFrame(out)
