"""Rolling realized volatility from daily closes."""

import numpy as np
import pandas as pd


def realized_volatility(
    close: pd.Series,
    window: int = 21,
    periods_per_year: int = 252,
) -> pd.Series:
    """Annualized rolling realized volatility.

    rv_t = sqrt( (periods_per_year / window) * sum_{i=t-window+1..t} r_i^2 )

    where r are daily log returns. Returns are not demeaned (standard for
    realized measures; the daily mean is negligible relative to volatility).
    min_periods equals the full window: a value is only reported when the
    window is completely observed, so data gaps produce honest NaNs instead
    of quietly less-precise estimates.
    """
    r = np.log(close.astype(float)).diff()
    rv2 = r.pow(2).rolling(window, min_periods=window).sum()
    return np.sqrt(rv2 * (periods_per_year / window)).rename("realized_vol")
