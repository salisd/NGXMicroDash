"""NGXDash — entry page: data coverage and project summary."""

import streamlit as st

from common import coverage, universe

st.set_page_config(page_title="NGXDash", page_icon="📊", layout="wide")

st.title("NGXDash — NGX Market Microstructure")
st.markdown(
    "Trade-based liquidity and volatility analytics for the **Nigerian "
    "Exchange (NGX)**: Roll (1984) and Corwin-Schultz (2012) bid-ask spread "
    "estimators, STL volume decomposition, and rolling realized volatility, "
    "computed from daily OHLCV. Use the pages in the sidebar; the "
    "**Methodology** page explains every estimator and its failure modes."
)

uni = universe()
cov = coverage()

st.subheader("Data status")
if uni is None:
    st.warning(
        "Universe not fetched yet. Run `python scripts/fetch_data.py` "
        "(the universe/sector table comes from NGX's public API, no key needed)."
    )
elif cov.empty:
    st.info(
        f"Universe cached: {len(uni)} listed equities across "
        f"{uni['sector'].nunique()} official NGX sectors — but no price "
        "history yet. Run `python scripts/fetch_data.py` with an API key "
        "configured (see README)."
    )
    st.dataframe(
        uni.groupby("sector").agg(listings=("symbol", "count")).reset_index(),
        use_container_width=True,
    )
else:
    left, right = st.columns(2)
    left.metric("Symbols cached", len(cov))
    right.metric(
        "Date range",
        f"{cov['first_date'].min()} → {cov['last_date'].max()}",
    )
    st.markdown(
        "**Coverage per symbol** — `missing_days` counts weekdays inside the "
        "range with no observation (NGX holidays *and* genuine gaps; we do "
        "not interpolate either). `has_high_low` determines whether "
        "Corwin-Schultz is computable."
    )
    st.dataframe(cov, use_container_width=True, hide_index=True)
