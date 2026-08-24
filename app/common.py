"""Shared data-loading and chart helpers for the Streamlit pages."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from ngxdash import config
from ngxdash.ingestion import cache


@st.cache_data(ttl=3600)
def universe() -> pd.DataFrame | None:
    return cache.load_universe()


@st.cache_data(ttl=3600)
def prices(symbol: str) -> pd.DataFrame | None:
    return cache.load_prices(symbol)


@st.cache_data(ttl=3600)
def coverage() -> pd.DataFrame:
    return cache.coverage_summary()


def cached_universe_rows() -> pd.DataFrame:
    """Universe rows restricted to symbols with cached price history."""
    uni = universe()
    syms = cache.cached_symbols()
    if uni is None or not syms:
        return pd.DataFrame()
    return uni[uni["symbol"].isin(syms)].reset_index(drop=True)


def require_data() -> pd.DataFrame:
    """Stop the page with instructions if the cache is empty."""
    rows = cached_universe_rows()
    if rows.empty:
        st.warning(
            "No cached price data found. Populate the cache first:\n\n"
            "```\npython scripts/fetch_data.py\n```\n\n"
            "You need an API key for NGX Pulse (`NGX_PULSE_API_KEY`) or "
            "EODHD (`EODHD_API_TOKEN`) in your environment or `.env` — "
            "see the README for how to get one. The dashboard itself never "
            "calls remote APIs."
        )
        st.stop()
    return rows


def spread_windows_sidebar():
    st.sidebar.header("Estimator windows")
    roll_w = st.sidebar.slider("Roll window (days)", 20, 250, config.DEFAULT_ROLL_WINDOW, 5)
    cs_w = st.sidebar.slider("Corwin-Schultz avg window (days)", 5, 120, config.DEFAULT_CS_WINDOW, 1)
    rv_w = st.sidebar.slider("Realized vol window (days)", 5, 250, config.DEFAULT_RV_WINDOW, 1)
    return roll_w, cs_w, rv_w
