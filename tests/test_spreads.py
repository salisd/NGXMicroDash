"""Estimator correctness against small hand-computed examples.

Expected values were computed by hand (explicit arithmetic on the published
formulas) before the library was written; see comments on each case.
"""

import math

import numpy as np
import pandas as pd
import pytest

from ngxdash.analytics.spreads import (
    corwin_schultz_series,
    cs_two_day,
    roll_spread,
    roll_spread_series,
)


def _idx(n):
    return pd.bdate_range("2024-01-01", periods=n)


class TestRoll:
    def test_alternating_bounce_matches_hand_computed_cov(self):
        # Trades alternating between ask=101 and bid=99.
        # dP = [-2, 2, -2, 2, -2, 2]; pairs (dP_t, dP_{t-1}):
        # x = [2,-2,2,-2,2], y = [-2,2,-2,2,-2]; sample cov (ddof=1) = -4.8
        # spread = 2*sqrt(4.8) = 4.381780460041...
        prices = pd.Series([101, 99, 101, 99, 101, 99, 101], index=_idx(7))
        spread, autocov = roll_spread(prices, use_log=False)
        assert autocov == pytest.approx(-4.8)
        assert spread == pytest.approx(2 * math.sqrt(4.8))

    def test_positive_autocov_is_flagged_not_faked(self):
        # Steady trend: dP constant -> autocovariance exactly 0 -> undefined.
        prices = pd.Series(np.arange(1.0, 11.0), index=_idx(10))
        spread, autocov = roll_spread(prices, use_log=False)
        assert autocov == pytest.approx(0.0)
        assert math.isnan(spread)

    def test_rolling_valid_flag(self):
        rng = np.random.default_rng(7)
        # Simulated Roll model: mid random walk + bid-ask bounce, spread 2%.
        n, half = 400, 0.01
        mid = 100 * np.exp(np.cumsum(rng.normal(0, 0.005, n)))
        q = rng.choice([-1.0, 1.0], n)
        prices = pd.Series(mid * (1 + q * half), index=_idx(n))
        out = roll_spread_series(prices, window=100)
        assert set(out.columns) == {"autocov", "spread", "valid"}
        # Where valid, the recovered proportional spread should be near 2%.
        est = out.loc[out["valid"], "spread"]
        assert len(est) > 50
        assert est.median() == pytest.approx(0.02, rel=0.35)
        # Spread must be NaN exactly where invalid (after warmup).
        warm = out.dropna(subset=["autocov"])
        assert warm.loc[~warm["valid"], "spread"].isna().all()

    def test_log_spread_is_proportional(self):
        prices = pd.Series([101.0, 99, 101, 99, 101, 99, 101], index=_idx(7))
        s_log, _ = roll_spread(prices, use_log=True)
        s_lvl, _ = roll_spread(prices, use_log=False)
        assert s_log == pytest.approx(s_lvl / 100, rel=0.01)


class TestCorwinSchultz:
    def test_two_day_hand_computed_positive(self):
        # H1=L1'=... identical days (52, 49, 52, 49):
        # beta = 2*ln(52/49)^2 = 0.007062285801
        # gamma = ln(52/49)^2  = 0.003531142900
        # alpha = (sqrt(2b)-sqrt(b))/(3-2*sqrt(2)) - sqrt(g/(3-2*sqrt(2)))
        #       = 0.059423420471; S = 2(e^a-1)/(1+e^a) = 0.059405940594
        assert cs_two_day(52, 49, 52, 49) == pytest.approx(0.059405940594, abs=1e-9)

    def test_two_day_hand_computed_negative(self):
        # (51, 49, 52, 50): beta=0.003138691138, gamma=0.003531142900,
        # alpha=-0.008206871808 -> S = -0.008206825745 (legitimately < 0).
        assert cs_two_day(51, 49, 52, 50) == pytest.approx(-0.008206825745, abs=1e-9)

    def test_series_matches_pointwise_and_zeroes_negatives(self):
        high = pd.Series([51.0, 52.0, 52.0], index=_idx(3))
        low = pd.Series([49.0, 50.0, 49.0], index=_idx(3))
        out = corwin_schultz_series(high, low, window=2, overnight_adjust=False)
        # Estimate indexed at the SECOND day of each pair.
        assert math.isnan(out["cs_raw"].iloc[0])
        assert out["cs_raw"].iloc[1] == pytest.approx(cs_two_day(51, 49, 52, 50), abs=1e-12)
        assert out["cs_raw"].iloc[2] == pytest.approx(cs_two_day(52, 50, 52, 49), abs=1e-12)
        # negative="zero" default: raw negative preserved, cs floored at 0.
        assert out["cs_raw"].iloc[1] < 0
        assert out["cs"].iloc[1] == 0.0

    def test_zero_range_days_masked(self):
        # Day 2 trades at a single price (H == L): both pairs touching it
        # must be masked, not reported as zero spread.
        high = pd.Series([51.0, 50.0, 52.0], index=_idx(3))
        low = pd.Series([49.0, 50.0, 49.0], index=_idx(3))
        out = corwin_schultz_series(high, low, window=2, overnight_adjust=False)
        assert math.isnan(out["cs"].iloc[1])
        assert math.isnan(out["cs"].iloc[2])

    def test_overnight_gap_adjustment(self):
        # Day 2 gaps up: its range [60, 62] lies entirely above day 1's
        # close 50. With adjustment, day 2's range is shifted down by
        # L2 - C1 = 10 -> pair becomes (51,49,52,50): S = cs_two_day(...).
        high = pd.Series([51.0, 62.0], index=_idx(2))
        low = pd.Series([49.0, 60.0], index=_idx(2))
        close = pd.Series([50.0, 61.0], index=_idx(2))
        adj = corwin_schultz_series(high, low, close, window=2, overnight_adjust=True)
        assert adj["cs_raw"].iloc[1] == pytest.approx(cs_two_day(51, 49, 52, 50), abs=1e-12)
        raw = corwin_schultz_series(high, low, close, window=2, overnight_adjust=False)
        assert raw["cs_raw"].iloc[1] != pytest.approx(adj["cs_raw"].iloc[1], abs=1e-6)
