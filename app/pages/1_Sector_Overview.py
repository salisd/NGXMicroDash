"""Sector overview: liquidity, volume, and volatility aggregated by sector."""

import plotly.graph_objects as go
import streamlit as st

from common import prices, require_data, spread_windows_sidebar
from ngxdash.aggregate import sector_median, sector_sum
from ngxdash.analytics import (
    corwin_schultz_series,
    decompose_volume,
    realized_volatility,
    roll_spread_series,
)

st.set_page_config(page_title="Sector Overview — NGXDash", layout="wide")
st.title("Sector overview")

rows = require_data()
roll_w, cs_w, rv_w = spread_windows_sidebar()
min_members = st.sidebar.slider(
    "Min constituents per sector-date", 1, 6, 3,
    help="Sector lines are hidden on dates with fewer reporting members, "
         "so an aggregate never quietly becomes a single stock.",
)

sectors = sorted(rows["sector"].unique())
chosen = st.multiselect("Sectors", sectors, default=sectors)
rows = rows[rows["sector"].isin(chosen)]
sector_of = dict(zip(rows["symbol"], rows["sector"]))

roll_p, cs_p, rv_p, vol_p = {}, {}, {}, {}
skipped_cs = []
for sym in rows["symbol"]:
    df = prices(sym)
    if df is None or len(df) < roll_w:
        continue
    roll_p[sym] = roll_spread_series(df["close"], window=roll_w)["spread"]
    rv_p[sym] = realized_volatility(df["close"], window=rv_w)
    vol_p[sym] = df["volume"]
    if df["high"].notna().any():
        cs_p[sym] = corwin_schultz_series(
            df["high"], df["low"], df["close"], window=cs_w
        )["cs_avg"]
    else:
        skipped_cs.append(sym)

if skipped_cs:
    st.caption(
        f"Corwin-Schultz unavailable for {', '.join(skipped_cs)} — the data "
        "source provided no high/low prices for them."
    )


def _plot(df, title, yfmt=".2%"):
    fig = go.Figure()
    for col in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col], name=col, mode="lines", connectgaps=False,
        ))
    fig.update_layout(
        title=title, hovermode="x unified", yaxis_tickformat=yfmt,
        legend=dict(orientation="h", y=-0.2), height=420, margin=dict(t=50),
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    st.plotly_chart(fig, use_container_width=True)


tab_liq, tab_vol, tab_rv = st.tabs(["Liquidity (spreads)", "Volume", "Realized volatility"])

with tab_liq:
    if cs_p:
        _plot(
            sector_median(cs_p, sector_of, min_members),
            f"Median Corwin-Schultz spread by sector ({cs_w}d avg)",
        )
    _plot(
        sector_median(roll_p, sector_of, min_members),
        f"Median Roll spread by sector ({roll_w}d rolling, valid windows only)",
    )
    st.caption(
        "Roll estimates exist only where price-change autocovariance is "
        "negative; on thin names that can be a minority of windows. See "
        "Methodology."
    )

with tab_vol:
    sec_vol = sector_sum(vol_p, sector_of)
    _plot(sec_vol, "Total traded volume by sector (shares/day)", yfmt="~s")
    st.markdown("**STL trend of sector volume** (loess trend of log1p volume)")
    trend_fig = go.Figure()
    for sector in sec_vol.columns:
        s = sec_vol[sector].dropna()
        if len(s) < 30:
            continue
        dec = decompose_volume(s, period=5)
        trend_fig.add_trace(go.Scatter(
            x=dec.index, y=dec["trend"], name=sector, mode="lines",
        ))
    trend_fig.update_layout(
        yaxis_title="log(1 + volume)", hovermode="x unified", height=420,
        legend=dict(orientation="h", y=-0.2), margin=dict(t=30),
    )
    trend_fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    st.plotly_chart(trend_fig, use_container_width=True)

with tab_rv:
    _plot(
        sector_median(rv_p, sector_of, min_members),
        f"Median constituent realized volatility by sector ({rv_w}d, annualized)",
    )
    st.caption(
        "Median across constituent stocks — deliberately *not* the vol of a "
        "sector portfolio, which would be lower through diversification."
    )
