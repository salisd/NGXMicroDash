"""Headless smoke tests: every dashboard page must run without exceptions.

Uses SYNTHETIC fixture data written to a temporary cache directory — this is
test scaffolding for exercising the UI code paths, entirely separate from the
real data/ cache the dashboard serves.
"""

import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).resolve().parent.parent / "app"
# streamlit run adds the main-script dir to sys.path; AppTest does not.
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture()
def synthetic_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("NGXDASH_DATA_DIR", str(tmp_path))
    from ngxdash import config

    importlib.reload(config)
    from ngxdash.ingestion import cache

    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2023-01-02", periods=300)
    symbols = {
        "AAA": "FINANCIAL SERVICES", "BBB": "FINANCIAL SERVICES",
        "CCC": "FINANCIAL SERVICES", "DDD": "CONSUMER GOODS",
        "EEE": "CONSUMER GOODS", "FFF": "CONSUMER GOODS",
    }
    cache.save_universe(pd.DataFrame({
        "symbol": list(symbols),
        "name": [f"{s} Plc" for s in symbols],
        "sector": list(symbols.values()),
        "market": "Main Board",
        "value_traded": 1e6,
    }))
    for i, sym in enumerate(symbols):
        mid = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))
        close = mid * (1 + rng.choice([-1, 1], len(idx)) * 0.01)
        high = close * (1 + rng.uniform(0.001, 0.02, len(idx)))
        low = close * (1 - rng.uniform(0.001, 0.02, len(idx)))
        df = pd.DataFrame(
            {"open": close, "high": high, "low": low, "close": close,
             "volume": rng.integers(0, 1_000_000, len(idx)).astype(float)},
            index=idx,
        )
        df.index.name = "date"
        cache.save_prices(sym, df, "synthetic-test")
    # Streamlit AppTest reuses this process; drop cached loaders so pages
    # see the temp dir.
    for mod in ("common",):
        sys.modules.pop(mod, None)
    yield tmp_path
    sys.modules.pop("common", None)
    importlib.reload(config)


def _run(page: str, cache_dir) -> AppTest:
    at = AppTest.from_file(str(APP_DIR / page), default_timeout=60)
    at.run()
    return at


@pytest.mark.parametrize(
    "page",
    ["streamlit_app.py", "pages/1_Sector_Overview.py",
     "pages/2_Security_Drilldown.py", "pages/3_Methodology.py"],
)
def test_page_runs_clean(page, synthetic_cache):
    at = _run(page, synthetic_cache)
    assert not at.exception, f"{page} raised: {[e.value for e in at.exception]}"
