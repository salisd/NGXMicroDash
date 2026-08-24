"""Methodology notes — written to be defensible in an interview."""

import streamlit as st

st.set_page_config(page_title="Methodology — NGXDash", layout="wide")
st.title("Methodology")

st.markdown(r"""
## Why trade-based estimators?

NGX does not expose free, high-quality **quote** (bid/ask) data, so effective
spreads here are estimated from **trades only** — daily OHLCV. This is a
standard, well-published constraint in emerging-market microstructure
research, and the two estimators below are the canonical tools for it.

---

## Roll (1984) — spread from serial covariance

**Idea.** If trades bounce randomly between bid and ask around a fixed mid,
consecutive price *changes* are negatively autocorrelated: a trade at the ask
followed by one at the bid mechanically reverses part of the previous change.

$$ S = 2\sqrt{-\,\mathrm{Cov}(\Delta p_t,\ \Delta p_{t-1})} $$

We use **log prices**, so \(S\) is a *proportional* spread, comparable across
securities. Rolling windows (configurable) give a time series.

**Assumptions.** (i) informational efficiency — the mid follows a random walk;
(ii) trades hit bid/ask with equal probability, independently over time;
(iii) the spread is constant within the window.

**Failure mode on NGX (important).** The estimator is only defined when the
autocovariance is **negative**. On thinly traded names, days without trades,
price momentum, or one-sided order flow easily push the autocovariance
non-negative. We **flag** those windows as invalid and show gaps — never a
zero, NaN-silently, or \( \sqrt{\text{negative}} \) garbage. The drill-down
page reports the share of valid windows so you can judge how much to trust
the series.

---

## Corwin–Schultz (2012) — spread from high/low ranges

**Idea.** The daily high is (almost always) a buyer-initiated trade at the ask
and the daily low a seller-initiated trade at the bid. The high–low ratio
therefore reflects *both* fundamental volatility *and* the spread. Volatility
scales with time while the spread does not, so comparing single-day ranges
with the two-day range separates the two.

With \( \beta = \sum_{j=0}^{1} \ln(H_{t+j}/L_{t+j})^2 \) and
\( \gamma = \ln(H_{t,t+1}/L_{t,t+1})^2 \) (two-day high over two-day low):

$$ \alpha = \frac{\sqrt{2\beta}-\sqrt{\beta}}{3-2\sqrt{2}} -
\sqrt{\frac{\gamma}{3-2\sqrt{2}}}, \qquad
S = \frac{2(e^{\alpha}-1)}{1+e^{\alpha}} $$

Per the paper we: (a) adjust the second day's range for **overnight gaps**
(if day \(t{+}1\)'s range sits entirely above/below day \(t\)'s close, it is
shifted by the gap); (b) floor **negative** two-day estimates at zero before
averaging — sampling error makes individual estimates noisy and the paper
recommends this for averaged series (the raw signed series is kept too);
(c) we additionally **mask days with zero high–low range** — on NGX these
are typically days with a handful of trades at one price, which would
otherwise masquerade as zero spread.

**Assumptions.** Continuous trading within the day (violated on thin NGX
names — infrequent trading makes observed highs/lows *narrower* than true
ranges, biasing the spread down), no large overnight news, highs/lows not
distorted by price limits.

**Cross-check.** The dashboard plots Roll and Corwin–Schultz side by side.
Broad agreement in level/trend is reassuring; divergence usually means thin
trading is breaking one estimator's assumptions (often Roll's first).

---

## Volume decomposition — STL

Daily volume is split into **trend + seasonal (5-day trading week) +
residual** with STL (Cleveland et al., 1990; `statsmodels`).

**Why STL over classical decomposition:** NGX volume is non-stationary — the
level and the amplitude of the weekly pattern both drift — and classical
moving-average decomposition assumes a fixed seasonal component.
STL fits trend and seasonality by loess so both can evolve, and the robust
variant downweights outliers (block trades) instead of letting one print
distort the whole seasonal estimate.

We decompose \( \log(1+V_t) \) — variance-stabilizing, and defined on
zero-volume days. Components are shown in log space, labeled as such.
Missing days are **not interpolated**; the series is decomposed on observed
trading days, accepting a small phase shift at gaps rather than fabricating
data.

---

## Realized volatility

$$ RV_t = \sqrt{\frac{252}{w} \sum_{i=t-w+1}^{t} r_i^2 } $$

with daily log returns \(r\), window \(w\) configurable in the sidebar.
Returns are not demeaned (standard for realized measures). A value is
reported **only when the full window is observed** — gaps in the data become
gaps in the vol series instead of quietly less-precise estimates.

---

## Honesty about data

* Nothing is interpolated or forward-filled, anywhere.
* `missing weekdays` counts include NGX public holidays — without a reliable
  free NGX holiday calendar we prefer over-reporting gaps to hiding real ones.
* Sector aggregates are **medians across constituents** and are suppressed on
  dates with fewer than a configurable number of members reporting.
* Sector classification comes from NGX's own public listing data, not a
  third-party mapping.

### References
* Roll, R. (1984). *A Simple Implicit Measure of the Effective Bid-Ask Spread
  in an Efficient Market.* Journal of Finance 39(4).
* Corwin, S. & Schultz, P. (2012). *A Simple Way to Estimate Bid-Ask Spreads
  from Daily High and Low Prices.* Journal of Finance 67(2).
* Cleveland, R. et al. (1990). *STL: A Seasonal-Trend Decomposition Procedure
  Based on Loess.* Journal of Official Statistics 6(1).
""")
