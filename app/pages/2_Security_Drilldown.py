"""Single-security drill-down: spreads, volume decomposition, realized vol."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from common import ensure_data, prices, require_data, spread_windows_sidebar
from ngxdash.analytics import (
    corwin_schultz_series,
    decompose_volume,
    realized_volatility,
    roll_spread_series,
)

st.set_page_config(page_title="Security Drill-down — NGXDash", layout="wide")
ensure_data()
st.title("Security drill-down")

rows = require_data()
roll_w, cs_w, rv_w = spread_windows_sidebar()

label = {
    r.symbol: f"{r.symbol} — {r.name} ({r.sector.title()})" for r in rows.itertuples()
}
sym = st.selectbox("Security", rows["symbol"], format_func=label.get)
df = prices(sym)

# Reindex onto the weekday calendar so charts show gaps instead of drawing
# through them. (Gaps include NGX public holidays — see Methodology.)
cal = pd.bdate_range(df.index.min(), df.index.max())
dfc = df.reindex(cal)

first, last = df.index.min().date(), df.index.max().date()
n_gap = len(cal) - len(df)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Observations", len(df))
c2.metric("Range", f"{first} → {last}")
c3.metric("Missing weekdays", n_gap, help="Includes NGX public holidays; nothing is interpolated.")
c4.metric("Zero-volume days", int((df["volume"] == 0).sum()))

# --- price & volume ---------------------------------------------------------
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
                    vertical_spacing=0.04)
fig.add_trace(go.Scatter(x=dfc.index, y=dfc["close"], name="close",
                         mode="lines", connectgaps=False), row=1, col=1)
fig.add_trace(go.Bar(x=dfc.index, y=dfc["volume"], name="volume"), row=2, col=1)
fig.update_layout(height=450, hovermode="x unified", showlegend=False,
                  title=f"{sym}: close (NGN) and traded volume", margin=dict(t=50))
fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
st.plotly_chart(fig, use_container_width=True)

tab_spread, tab_vol, tab_rv = st.tabs(
    ["Spread estimates", "Volume decomposition", "Realized volatility"]
)

with tab_spread:
    roll = roll_spread_series(dfc["close"], window=roll_w)
    have_hl = df["high"].notna().any()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=roll.index, y=roll["spread"], name=f"Roll ({roll_w}d)",
                             mode="lines", connectgaps=False))
    if have_hl:
        cs = corwin_schultz_series(dfc["high"], dfc["low"], dfc["close"], window=cs_w)
        fig.add_trace(go.Scatter(x=cs.index, y=cs["cs_avg"],
                                 name=f"Corwin-Schultz ({cs_w}d avg)",
                                 mode="lines", connectgaps=False))
    fig.update_layout(title="Proportional effective-spread estimates",
                      yaxis_tickformat=".2%", hovermode="x unified", height=420,
                      legend=dict(orientation="h", y=-0.2), margin=dict(t=50))
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    st.plotly_chart(fig, use_container_width=True)

    n_windows = int(roll["autocov"].notna().sum())
    n_valid = int(roll["valid"].sum())
    pct = 100 * n_valid / n_windows if n_windows else 0.0
    st.markdown(
        f"**Roll validity:** the estimator is defined (negative price-change "
        f"autocovariance) in **{n_valid} of {n_windows}** windows "
        f"(**{pct:.0f}%**). Invalid windows are shown as gaps, not zeros — "
        "on thinly traded NGX names, infrequent trading and momentum often "
        "overwhelm bid-ask bounce. See Methodology."
    )
    if have_hl and not np.isnan(cs["cs_avg"]).all():
        masked = float(cs["pct_masked"].iloc[-1] or 0)
        st.markdown(
            f"**Corwin-Schultz:** negative two-day estimates are floored at "
            f"zero before averaging (per the paper); days with zero "
            f"high-low range are masked (recently ~{masked:.0%} of days)."
        )
    if not have_hl:
        st.info("No high/low data from the source for this symbol — "
                "Corwin-Schultz is not computable and is not faked.")

with tab_vol:
    v = df["volume"].dropna()
    if len(v) < 30:
        st.info("Not enough observations for STL decomposition (need ≥ 30).")
    else:
        dec = decompose_volume(v, period=5)
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                            subplot_titles=["observed", "trend", "seasonal (5-day)", "residual"],
                            vertical_spacing=0.06)
        for i, col in enumerate(["observed", "trend", "seasonal", "resid"], start=1):
            fig.add_trace(go.Scatter(x=dec.index, y=dec[col], mode="lines",
                                     showlegend=False), row=i, col=1)
        fig.update_layout(height=700, title="STL decomposition of log(1 + volume)",
                          margin=dict(t=60))
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Decomposed on observed trading days (period = 5, the trading "
            "week), robust loess. Gaps are not interpolated; a long gap "
            "slightly shifts the weekly phase rather than inventing data."
        )

with tab_rv:
    rv = realized_volatility(dfc["close"], window=rv_w)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rv.index, y=rv, mode="lines", connectgaps=False))
    fig.update_layout(title=f"Rolling {rv_w}d realized volatility (annualized)",
                      yaxis_tickformat=".0%", height=420, margin=dict(t=50))
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "√(252/w · Σ r²) over daily log returns; a value is reported only "
        "when the full window is observed, so data gaps propagate to honest "
        "gaps here."
    )
