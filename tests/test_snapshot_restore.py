"""Tests for the bundled-snapshot restore path that first boot depends on.

Uses a small synthetic snapshot in a temp dir — this is scaffolding to
exercise cache.restore_from_snapshot() in isolation, not the real
data_snapshot/ shipped with the app.
"""

import importlib
import json

import numpy as np
import pandas as pd
import pytest


@pytest.fixture()
def synthetic_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("NGXDASH_DATA_DIR", str(tmp_path / "runtime"))
    from ngxdash import config

    importlib.reload(config)
    monkeypatch.setattr(config, "SNAPSHOT_DIR", tmp_path / "snapshot")

    from ngxdash.ingestion import cache

    importlib.reload(cache)

    snap = tmp_path / "snapshot"
    (snap / "prices").mkdir(parents=True)
    idx = pd.bdate_range("2024-01-02", periods=10)
    df = pd.DataFrame(
        {"open": np.nan, "high": np.nan, "low": np.nan,
         "close": np.arange(10.0), "volume": np.arange(10.0) * 1000},
        index=idx,
    )
    df.index.name = "date"
    df.to_parquet(snap / "prices" / "AAA.parquet")
    pd.DataFrame({"symbol": ["AAA"], "name": ["AAA Plc"],
                  "sector": ["BANKS"], "market": ["Main"],
                  "value_traded": [1.0]}).to_parquet(snap / "universe.parquet")
    (snap / "meta.json").write_text(json.dumps({"symbols": {"AAA": {}}}))
    (snap / "SNAPSHOT_INFO.json").write_text(
        json.dumps({"as_of": "2024-01-15", "n_symbols": 1, "reason": "test"})
    )
    yield cache, config
    importlib.reload(config)
    importlib.reload(cache)


def test_restore_populates_empty_runtime_cache(synthetic_snapshot):
    cache, config = synthetic_snapshot
    assert cache.cached_symbols() == []
    manifest = cache.restore_from_snapshot()
    assert manifest == {"as_of": "2024-01-15", "n_symbols": 1, "reason": "test"}
    assert cache.cached_symbols() == ["AAA"]
    df = cache.load_prices("AAA")
    assert len(df) == 10
    assert cache.load_universe() is not None


def test_restore_returns_none_without_bundled_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("NGXDASH_DATA_DIR", str(tmp_path / "runtime"))
    from ngxdash import config

    importlib.reload(config)
    monkeypatch.setattr(config, "SNAPSHOT_DIR", tmp_path / "nonexistent")
    from ngxdash.ingestion import cache

    importlib.reload(cache)
    assert cache.restore_from_snapshot() is None
    importlib.reload(config)
    importlib.reload(cache)
