import pandas as pd

from ngxdash.aggregate import sector_median, sector_sum

IDX = pd.bdate_range("2024-01-01", periods=4)
SECTOR_OF = {"A": "BANKS", "B": "BANKS", "C": "BANKS", "D": "OIL"}


def _series(vals):
    return pd.Series(vals, index=IDX, dtype="float64")


def test_median_requires_min_constituents():
    per_symbol = {
        "A": _series([1, 2, None, 4]),
        "B": _series([3, 4, 5, 6]),
        "C": _series([5, 6, 7, None]),
        "D": _series([9, 9, 9, 9]),
    }
    out = sector_median(per_symbol, SECTOR_OF, min_constituents=3)
    assert out.loc[IDX[0], "BANKS"] == 3.0
    assert pd.isna(out.loc[IDX[2], "BANKS"])  # only 2 banks observed
    # OIL has a single constituent < 3 -> never reported
    assert out["OIL"].isna().all()


def test_sum_for_volume():
    per_symbol = {"A": _series([1, 2, 3, 4]), "B": _series([10, None, 30, 40])}
    out = sector_sum(per_symbol, {"A": "BANKS", "B": "BANKS"})
    assert out.loc[IDX[0], "BANKS"] == 11.0
    assert out.loc[IDX[1], "BANKS"] == 2.0  # missing treated as absent, not zero
