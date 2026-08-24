import numpy as np
import pandas as pd
import pytest

from ngxdash.analytics.decomposition import decompose_volume


def _weekly_volume(n=200, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-02", periods=n)
    weekday = np.array([d.weekday() for d in idx])
    seasonal = np.array([0.3, 0.0, -0.1, 0.0, 0.4])[weekday]  # Mon/Fri heavier
    trend = np.linspace(11, 12, n)
    log_v = trend + seasonal + rng.normal(0, 0.05, n)
    return pd.Series(np.expm1(log_v).round(), index=idx, name="volume")


def test_components_reconstruct_observed():
    v = _weekly_volume()
    out = decompose_volume(v, period=5)
    recon = out["trend"] + out["seasonal"] + out["resid"]
    assert np.allclose(recon, out["observed"], atol=1e-8)
    assert out.attrs["log"] is True


def test_recovers_weekly_pattern():
    v = _weekly_volume()
    out = decompose_volume(v, period=5)
    by_weekday = out["seasonal"].groupby(out.index.weekday).mean()
    # Friday (0.4) heaviest, Wednesday (-0.1) lightest, as constructed.
    assert by_weekday.idxmax() == 4
    assert by_weekday.idxmin() == 2


def test_rejects_short_series():
    v = _weekly_volume(n=20)
    with pytest.raises(ValueError, match="at least"):
        decompose_volume(v, period=5)


def test_rejects_negative_volume():
    v = _weekly_volume()
    v.iloc[5] = -1
    with pytest.raises(ValueError, match="non-negative"):
        decompose_volume(v, period=5)


def test_handles_zero_volume_days():
    v = _weekly_volume()
    v.iloc[10:15] = 0.0  # no-trade week: log1p must not blow up
    out = decompose_volume(v, period=5)
    assert np.isfinite(out.to_numpy()).all()
