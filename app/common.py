"""Shared data-loading and chart helpers for the Streamlit pages."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import threading

import pandas as pd
import streamlit as st

from ngxdash import bootstrap, config
from ngxdash.ingestion import cache


@st.cache_resource(show_spinner=False)
def _bootstrap_lock() -> threading.Lock:
    """One lock per server process, so concurrent first viewers cannot each
    start a fetch and double-spend the API rate limit."""
    return threading.Lock()


def ensure_data() -> None:
    """Fetch-on-first-boot: called at the top of every page.

    No-op whenever the cache has any symbols (the normal case — including
    every rerun and every later viewer). Only a genuinely empty cache with a
    configured key triggers a fetch, with visible progress. Without a key we
    fall through to the pages' "no data" guidance instead of hanging.
    """
    if not bootstrap.bootstrap_needed() or not config.NGX_PULSE_API_KEY:
        return
    lock = _bootstrap_lock()
    if not lock.acquire(blocking=False):
        st.info(
            "First-boot data fetch is running in another session — "
            "this page will load once it finishes. Refresh in a minute."
        )
        st.stop()
    try:
        if not bootstrap.bootstrap_needed():  # raced: another session finished
            return
        st.title("NGXDash — first boot")
        st.markdown(
            "The data cache is empty (fresh deployment), so ~9 years of "
            "daily NGX history is being fetched now. This respects the API's "
            "10 requests/minute limit, so it typically takes **4–10 "
            "minutes** depending on API response times — afterwards the app "
            "serves everything from its local cache."
        )
        bar = st.progress(0.0, text="Fetching NGX universe…")

        def _progress(done: int, total: int, msg: str) -> None:
            bar.progress(done / max(total, 1), text=msg)

        result = bootstrap.run_bootstrap(progress=_progress)
        if result["failed"]:
            names = ", ".join(s for s, _ in result["failed"])
            st.warning(
                f"{len(result['failed'])} symbol(s) could not be fetched and "
                f"are simply absent (not faked): {names}. A common cause is "
                "the API's 100 requests/day budget; they will be picked up "
                "on the next cold boot."
            )
        if result["fetched"] == 0:
            st.error(
                "Bootstrap fetched nothing — the app cannot render. "
                "Check the API key in secrets and the API status, then reboot."
            )
            st.stop()
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
