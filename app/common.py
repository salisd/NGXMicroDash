"""Shared data-loading and chart helpers for the Streamlit pages."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import threading

import pandas as pd
import streamlit as st

from ngxdash import config
from ngxdash.ingestion import cache


@st.cache_resource(show_spinner=False)
def _bootstrap_lock() -> threading.Lock:
    """One lock per server process, so concurrent first viewers on a cold
    container cannot both race the snapshot copy at once."""
    return threading.Lock()


def ensure_data() -> None:
    """First-boot data restore: called at the top of every page.

    No-op whenever the runtime cache already has any symbols (the normal
    case — every rerun, every later viewer, and every local dev session
    after the first `scripts/fetch_data.py` run).

    On a genuinely empty cache (a fresh Streamlit Cloud container, whose
    filesystem is ephemeral), this restores the bundled, versioned snapshot
    in data_snapshot/ rather than live-fetching. That used to be a live
    fetch from NGX Pulse, but NGX Pulse rebranded to Kobo Terminal and its
    free tier no longer serves more than 7 days of history (confirmed
    2026-09-16 — see README "Known limitations"), which is too little for
    any of the estimator windows. Restoring a dated snapshot and saying so
    honestly beats a live fetch that would silently under-deliver.
    """
    if cache.cached_symbols():
        return
    lock = _bootstrap_lock()
    if not lock.acquire(blocking=False):
        st.info("Restoring bundled dataset in another session — reloading…")
        st.stop()
    try:
        if cache.cached_symbols():  # raced: another session already restored
            return
        manifest = cache.restore_from_snapshot()
        if manifest is None:
            st.error(
                "No local data and no bundled snapshot found. Run "
                "`python scripts/fetch_data.py` locally to populate the "
                "cache (requires an API key — see README)."
            )
            st.stop()
        st.info(
            f"Restored the bundled dataset: {manifest.get('n_symbols', '?')} "
            f"symbols as of **{manifest.get('as_of', '?')}**. "
            f"{manifest.get('reason', '')} This is a frozen, versioned "
            "snapshot shipped with the app, not a live fetch — see the "
            "entry page and README for why."
        )
    finally:
        lock.release()
    st.cache_data.clear()
    st.rerun()


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
