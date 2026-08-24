"""Trade-based bid-ask spread estimators.

Two estimators that need only daily trade data (no quotes):

* Roll (1984): effective spread from the negative serial covariance of
  consecutive price changes.
* Corwin & Schultz (2012): spread from two-day high/low price ranges.

Both are documented in detail in the README methodology section, including
their failure modes on thin NGX trading.
"""

import numpy as np
import pandas as pd

# 3 - 2*sqrt(2), the constant from Corwin & Schultz (2012), eq. (14).
_CS_K = 3.0 - 2.0 * np.sqrt(2.0)


def roll_spread(close: pd.Series, use_log: bool = True) -> tuple[float, float]:
    """Full-sample Roll (1984) spread estimate.

    Returns (spread, autocov) where autocov is the first-order sample
    autocovariance of price changes. The spread is only defined when
    autocov < 0; otherwise spread is NaN. With use_log=True the input is
    log-transformed so the spread is proportional (comparable across
    securities); otherwise it is in price units.
    """
    p = np.log(close.astype(float)) if use_log else close.astype(float)
    dp = p.diff().dropna()
    if len(dp) < 3:
        return np.nan, np.nan
    x, y = dp.iloc[1:].to_numpy(), dp.iloc[:-1].to_numpy()
    autocov = np.cov(x, y, ddof=1)[0, 1]
    spread = 2.0 * np.sqrt(-autocov) if autocov < 0 else np.nan
    return spread, autocov


def roll_spread_series(
    close: pd.Series,
    window: int = 60,
    min_periods: int | None = None,
    use_log: bool = True,
) -> pd.DataFrame:
    """Rolling Roll (1984) spread.

    Columns:
      autocov  rolling first-order autocovariance of price changes
      spread   2*sqrt(-autocov) where autocov < 0, else NaN
      valid    True where the estimator is defined (autocov < 0)

    Windows where the autocovariance is non-negative are flagged invalid
    rather than silently dropped: on thinly traded NGX names positive
    autocovariance is common and economically meaningful (momentum /
    infrequent trading swamps bid-ask bounce).
    """
    if min_periods is None:
        min_periods = window
    p = np.log(close.astype(float)) if use_log else close.astype(float)
    dp = p.diff()
    autocov = dp.rolling(window, min_periods=min_periods).cov(dp.shift(1))
    valid = autocov < 0
    spread = pd.Series(np.nan, index=close.index)
    spread[valid] = 2.0 * np.sqrt(-autocov[valid])
    return pd.DataFrame({"autocov": autocov, "spread": spread, "valid": valid})


def cs_two_day(h1: float, l1: float, h2: float, l2: float) -> float:
    """Raw Corwin-Schultz (2012) spread for one two-day window.

    Implements eqs. (12), (14), (18) of the paper:
      beta  = ln(H1/L1)^2 + ln(H2/L2)^2
      gamma = ln(max(H1,H2)/min(L1,L2))^2
      alpha = (sqrt(2*beta) - sqrt(beta)) / (3 - 2*sqrt(2))
              - sqrt(gamma / (3 - 2*sqrt(2)))
      S     = 2*(e^alpha - 1) / (1 + e^alpha)

    Can legitimately be negative; the caller decides how to treat that.
    """
    beta = np.log(h1 / l1) ** 2 + np.log(h2 / l2) ** 2
    gamma = np.log(max(h1, h2) / min(l1, l2)) ** 2
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / _CS_K - np.sqrt(gamma / _CS_K)
    return float(2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha)))


def corwin_schultz_series(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series | None = None,
    window: int = 21,
    overnight_adjust: bool = True,
    negative: str = "zero",
    mask_zero_range: bool = True,
) -> pd.DataFrame:
    """Corwin-Schultz (2012) high-low spread estimator, vectorized.

    Each two-day estimate is indexed at the *second* day of its pair, so the
    rolling average at date t uses only information available at t.

    Parameters
    ----------
    close : optional; enables the paper's overnight-return adjustment.
        If day t+1's range lies entirely above (below) day t's close, both
        H and L of day t+1 are shifted down (up) by the gap, so overnight
        drift is not misread as intraday range.
    negative : how to treat negative two-day estimates in the averaged
        series: "zero" (paper's recommendation for averaging), "nan", or
        "keep". The raw series is always returned unmodified.
    mask_zero_range : mask two-day windows where either day has H == L.
        On NGX these are usually days with a handful of trades at one price;
        they would otherwise produce spurious zero spreads.

    Columns: cs_raw (2-day estimate), cs (after negative/zero-range
    treatment), cs_avg (rolling mean of cs over `window` days), pct_masked.
    """
    if negative not in {"zero", "nan", "keep"}:
        raise ValueError(f"negative must be zero|nan|keep, got {negative!r}")
    h = high.astype(float).copy()
    l = low.astype(float).copy()

    h2, l2 = h.copy(), l.copy()  # day-(t) values, possibly overnight-adjusted
    if overnight_adjust and close is not None:
        prev_close = close.astype(float).shift(1)
        gap_up = (l - prev_close).clip(lower=0)     # range entirely above prev close
        gap_down = (prev_close - h).clip(lower=0)   # range entirely below prev close
        shift = gap_down - gap_up
        h2 = h + shift
        l2 = l + shift

    # The paper adjusts only the second day of each pair; the first day
    # enters with its raw range.
    h1, l1 = h.shift(1), l.shift(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = np.log(h1 / l1) ** 2 + np.log(h2 / l2) ** 2
        gamma = np.log(np.maximum(h1, h2) / np.minimum(l1, l2)) ** 2
        alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / _CS_K - np.sqrt(gamma / _CS_K)
        cs_raw = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))

    zero_range = (h2 <= l2) | (h1 <= l1)
    cs = cs_raw.copy()
    if mask_zero_range:
        cs[zero_range] = np.nan
    if negative == "zero":
        cs[cs < 0] = 0.0
    elif negative == "nan":
        cs[cs < 0] = np.nan

    cs_avg = cs.rolling(window, min_periods=max(2, window // 2)).mean()
    pct_masked = zero_range.rolling(window, min_periods=1).mean()
    return pd.DataFrame(
        {"cs_raw": cs_raw, "cs": cs, "cs_avg": cs_avg, "pct_masked": pct_masked}
    )
