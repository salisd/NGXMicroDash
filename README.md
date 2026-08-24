# NGXDash — Market Microstructure on the Nigerian Exchange

A data pipeline and Streamlit dashboard analyzing **liquidity and volatility
on the Nigerian Exchange (NGX)** from daily OHLCV data: trade-based bid-ask
spread estimation (Roll 1984; Corwin–Schultz 2012), STL decomposition of
traded volume, and rolling realized volatility, aggregated by official NGX
sector.

## Why trade-based estimators?

NGX does not expose free, high-quality bid/ask quote data. Estimating
effective spreads from trades alone (daily OHLCV) is the standard approach in
emerging-market microstructure research, and that constraint shapes the whole
design: both estimators here are published, peer-reviewed proxies with known
assumptions and known failure modes on thin trading — all documented below
and in the dashboard's Methodology page.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API key(s)
```

### Data sources & keys

| Role | Source | Key | Notes |
|---|---|---|---|
| Universe & sectors | [NGX doclib REST](https://doclib.ngxgroup.com/REST/api/statistics/equities/) (the exchange's own public endpoint) | none | Official sector classification, 147 listed equities |
| Price history (primary) | [NGX Pulse](https://ngxpulse.ng/api) | `NGX_PULSE_API_KEY` — free Personal key, instant | Personal tier verified to serve daily history from 2017 — but **close + volume only** (no genuine open/high/low) |
| Price history (fallback) | [EODHD](https://eodhd.com/exchange/XNSA) (NGX = `XNSA`) | `EODHD_API_TOKEN` | Free tier 20 calls/day → fetch incrementally (`--max-symbols 18`), or the All-World plan |

### Fetch data (one-time; cached locally)

```bash
python scripts/fetch_data.py                 # auto-picks source from env keys
python scripts/fetch_data.py --source eodhd --max-symbols 18   # free-tier friendly
python scripts/fetch_data.py --symbols GTCO,DANGCEM,MTNN --start 2017-01-01
```

Everything lands in `data/` (parquet + a provenance `meta.json`). The fetch
is **incremental** — already-cached symbols are skipped — so tight free-tier
rate limits just mean running it on a couple of consecutive days. The
dashboard **never** calls remote APIs; it reads only the cache, so the
analysis is reproducible offline.

Default universe: top 6 symbols by traded value in each of 6 official NGX
sectors (Financial Services, Consumer Goods, Industrial Goods, Oil and Gas,
ICT, Agriculture) — configurable via `--sectors/--per-sector/--symbols`.

> **Achieved data (fetched 2026-08-24, NGX Pulse Personal key):** 36 symbols
> across 6 sectors, spanning up to **2015-01-05 → 2026-08-24** for the
> longest-listed names; newer listings start at their listing dates (e.g.
> MTNN 2019, BUAFOODS 2022). The depth the API serves has varied slightly
> between fetches (2017 vs 2015 starts); the entry page always reports the
> range actually in the cache, which is the number to quote.
> **The free tier returns close + volume history only** — its
> historical rows carry no genuine open/high/low (the API duplicates close
> into "open"; the ingestion nulls those columns rather than store
> fake OHLC). Consequently Corwin-Schultz cannot be computed from this
> source and the dashboard says so per symbol instead of faking it; Roll,
> STL volume decomposition, and realized volatility are unaffected. To light
> up Corwin-Schultz, supply high/low data (e.g. an EODHD key) for at least a
> subset of symbols.

### Deployment (Streamlit Community Cloud)

The app is deployed at: **<DEPLOY_URL>** (fill in after first deploy).

How the deployed instance stays honest and inside API limits:

* **Fetch-on-first-boot.** Streamlit Cloud's filesystem is ephemeral, so a
  fresh container starts with an empty cache. Every data page calls
  `ensure_data()`, which detects the empty cache and runs the same fetch
  pipeline as `scripts/fetch_data.py` (one shared implementation in
  `ngxdash/bootstrap.py`) with a visible progress bar — a cold visitor sees
  "first boot, fetching, ~4–10 minutes", never a blank page. Most-traded
  symbols are fetched first, so if the fetch is cut short the app degrades
  to partial coverage and says so.
* **Rate limits.** Boot fetches are spaced 6.5s apart (~9 req/min, under
  the Personal tier's 10/min cap) and a process-wide lock prevents
  concurrent viewers from double-fetching. One boot costs ~37 of the
  tier's 100 requests/day, so the tier supports at most ~2 cold boots per
  day — fine for a portfolio app that Streamlit keeps warm between visits,
  and a fetch that runs out of budget shows failed symbols explicitly.
* **Secrets.** The API key lives in Streamlit Cloud's secrets manager
  (Settings → Secrets): `NGX_PULSE_API_KEY = "..."`. Locally it comes from
  `.env`. Both go through one lookup path (`ngxdash/config.py`), so local
  and deployed behavior cannot drift.

To deploy your own: push to GitHub → share.streamlit.io → New app →
repo/branch `main`, main file `app/streamlit_app.py`, Python 3.13 → add the
secret above → Deploy.

### Run the dashboard

```bash
streamlit run app/streamlit_app.py
```

### Run the tests

```bash
pytest
```

The estimator math is tested against small hand-computed examples (explicit
arithmetic on the published formulas, computed before the library code was
written), plus recovery tests on simulated Roll-model prices and
known-volatility random walks.

## Repo layout

```
ngxdash/
  ingestion/     API clients (NGX Pulse, EODHD), NGX public universe, parquet cache
  analytics/     spreads.py (Roll, Corwin-Schultz), volatility.py, decomposition.py
  aggregate.py   sector-level aggregation rules
scripts/fetch_data.py   the only component that touches remote APIs
app/                    Streamlit: entry + Sector Overview / Drill-down / Methodology
tests/                  unit tests for estimators, ingestion, aggregation
```

## Methodology (summary — full version in the dashboard)

**Roll (1984).** `S = 2√(−Cov(Δp_t, Δp_{t−1}))` on log prices → proportional
spread. Defined **only** when the autocovariance is negative. On thin NGX
names it frequently isn't (infrequent trading and momentum swamp bid-ask
bounce); those windows are flagged invalid and shown as gaps — never zeros or
NaN-by-accident. The drill-down reports the % of valid windows.

**Corwin–Schultz (2012).** Two-day high/low estimator (β/γ/α exactly as in
the paper, constant 3−2√2), with the paper's overnight-gap adjustment,
negatives floored at zero before averaging (raw signed series retained), and
zero-range days masked (thin-trading artifact that fakes zero spreads).
Known bias: infrequent trading narrows observed ranges → underestimates.
Plotted against Roll as a mutual sanity check; divergence usually means thin
trading is breaking one estimator's assumptions.

**STL volume decomposition.** `log1p(volume)` → trend + 5-day seasonal +
residual, robust loess. Chosen over classical decomposition because NGX
volume is non-stationary with drifting seasonal amplitude, and robust STL
downweights block-trade outliers. Gaps are not interpolated.

**Realized volatility.** `√((252/w)·Σr²)` on daily log returns, window
configurable in the UI; reported only for fully observed windows.

**Sector aggregation.** Median across constituents (spreads, vol), sum
(volume); suppressed below a minimum constituent count. Median-of-vols is
labeled as "typical constituent volatility", *not* portfolio vol.

**Missing data policy.** Nothing is interpolated or forward-filled anywhere.
Reported gap counts include NGX public holidays (no reliable free holiday
calendar; over-reporting gaps beats hiding real ones).

## Known limitations

* NGX Pulse free tier provides no historical high/low → Corwin-Schultz
  runs only for symbols with high/low from another source (none in the
  default fetch); it remains fully implemented, unit-tested, and documented.
* Daily (not intraday) data → both spread estimators are proxies, and
  Corwin–Schultz systematically *under*-estimates on infrequently traded
  names; Roll is often undefined on them. This is a property of the setting,
  and the dashboard surfaces it rather than smoothing it over.
* NGX Pulse's historical response schema isn't publicly documented for the
  free tier; the ingestion is schema-tolerant and fails loudly (never
  silently) when a key returns snapshots only.
* No survivorship-bias handling: the universe is today's listings.

## References

Roll (1984), *J. Finance* 39(4) · Corwin & Schultz (2012), *J. Finance*
67(2) · Cleveland et al. (1990), *J. Official Statistics* 6(1).
