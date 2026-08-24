"""Volume time-series decomposition via STL."""

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL


def decompose_volume(
    volume: pd.Series,
    period: int = 5,
    log: bool = True,
    robust: bool = True,
) -> pd.DataFrame:
    """STL decomposition of a daily traded-volume series.

    Why STL over classical decomposition: NGX volume is non-stationary
    (trend and seasonal amplitude drift over time) and has large outliers
    (block trades). STL fits the trend and seasonal components with loess,
    letting both evolve, and robust=True downweights outliers instead of
    letting one block trade distort the seasonal pattern.

    The series is decomposed on *observed trading days* in sequence, with
    period=5 capturing the trading-week (Mon-Fri) cycle. Missing days are
    not interpolated: gaps shift the phase of the weekly cycle slightly,
    which we accept rather than fabricate data.

    log=True decomposes log1p(volume) (variance-stabilizing, handles
    zero-volume days); components are then additive in log space. The
    returned frame carries attrs["log"] so callers can label axes honestly.

    Columns: observed, trend, seasonal, resid (all in log1p space when
    log=True).
    """
    v = volume.astype(float).dropna()
    if (v < 0).any():
        raise ValueError("volume must be non-negative")
    min_len = 6 * period
    if len(v) < min_len:
        raise ValueError(
            f"need at least {min_len} observations for STL with period={period}, "
            f"got {len(v)}"
        )
    y = np.log1p(v) if log else v
    res = STL(y.to_numpy(), period=period, robust=robust).fit()
    out = pd.DataFrame(
        {
            "observed": y.to_numpy(),
            "trend": res.trend,
            "seasonal": res.seasonal,
            "resid": res.resid,
        },
        index=v.index,
    )
    out.attrs["log"] = log
    return out
