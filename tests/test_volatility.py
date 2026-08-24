import math

import numpy as np
import pandas as pd
import pytest

from ngxdash.analytics.volatility import realized_volatility


def _idx(n):
    return pd.bdate_range("2024-01-01", periods=n)


def test_hand_computed_three_day_window():
    # closes [100, 102, 101, 103]:
    # r = [ln(1.02), ln(101/102), ln(103/101)]
    # rv = sqrt((252/3) * sum(r^2)) = 0.2709079755757977
    close = pd.Series([100.0, 102.0, 101.0, 103.0], index=_idx(4))
    rv = realized_volatility(close, window=3)
    assert math.isnan(rv.iloc[0]) and math.isnan(rv.iloc[1]) and math.isnan(rv.iloc[2])
    assert rv.iloc[3] == pytest.approx(0.2709079755757977, abs=1e-12)


def test_constant_price_zero_vol():
    close = pd.Series(50.0, index=_idx(30))
    rv = realized_volatility(close, window=10)
    assert (rv.dropna() == 0).all()


def test_recovers_known_annualized_vol():
    rng = np.random.default_rng(11)
    sigma_daily = 0.30 / math.sqrt(252)
    close = pd.Series(
        100 * np.exp(np.cumsum(rng.normal(0, sigma_daily, 5000))), index=_idx(5000)
    )
    rv = realized_volatility(close, window=252)
    assert rv.dropna().mean() == pytest.approx(0.30, rel=0.05)


def test_incomplete_window_is_nan_not_partial():
    close = pd.Series([100.0, 101.0, 102.0], index=_idx(3))
    rv = realized_volatility(close, window=5)
    assert rv.isna().all()
