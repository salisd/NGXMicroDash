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

> **Achieved data — frozen snapshot as of 2026-08-24** (NGX Pulse Personal
> key, fetched before the vendor tier change below): 36 symbols across 6
> sectors, spanning up to **2015-01-05 → 2026-08-24** for the longest-listed
> names; newer listings start at their listing dates (e.g. MTNN 2019,
> BUAFOODS 2022). The entry page always reports the range actually in the
> cache, which is the number to quote.
> **The free tier returns close + volume history only** — its
> historical rows carry no genuine open/high/low (the API duplicates close
> into "open"; the ingestion nulls those columns rather than store
> fake OHLC). Consequently Corwin-Schultz cannot be computed from this
> source and the dashboard says so per symbol instead of faking it; Roll,
> STL volume decomposition, and realized volatility are unaffected. To light
> up Corwin-Schultz, supply high/low data (e.g. an EODHD key) for at least a
> subset of symbols.
>
> **Why this data no longer refreshes (vendor change, 2026-09-16):** NGX
> Pulse rebranded to **Kobo Terminal** (koboterminal.com, operated by
> SereneCircle Limited) and closed a loophole — its free tier now returns
> `403 Starter plan required for historical data` for any request beyond 7
> days of history, confirmed directly against the live API with the same
> key that fetched everything above. The 36-symbol dataset above was
> fetched legitimately while the free tier still served full history, and
> is committed to this repo as a dated, versioned snapshot (`data_snapshot/`,
> see `SNAPSHOT_INFO.json`) rather than re-fetched live. Extending it now
> requires either the ₦29,000/month Starter tier or a different source.

### Deployment (Streamlit Community Cloud)

The app is deployed at: **<DEPLOY_URL>** (fill in after first deploy).

How the deployed instance stays honest given the vendor change above:

* **Restore-on-first-boot, not fetch-on-first-boot.** Streamlit Cloud's
  filesystem is ephemeral, so a fresh container starts with an empty cache.
  This was originally designed as a live fetch on first boot, but the free
  tier's 7-day cap (see above) makes that produce a dashboard with too
  little history for any estimator window. Instead, every data page calls
  `ensure_data()` (`app/common.py`), which detects an empty runtime cache
  and restores the committed `data_snapshot/` into it
  (`ngxdash.ingestion.cache.restore_from_snapshot`) — a local file copy,
  not a network call, so it's near-instant and cannot be rate-limited. The
  restored page tells the viewer plainly that this is a dated snapshot, not
  live data. `ngxdash/bootstrap.py` still contains the original live-fetch
  logic, kept for local use if you're on a paid tier (see its module
  docstring) — it is not what the deployed app relies on.
* **Secrets.** The API key lives in Streamlit Cloud's secrets manager
  (Settings → Secrets): `NGX_PULSE_API_KEY = "..."`. Locally it comes from
  `.env`. Both go through one lookup path (`ngxdash/config.py`), so local
  and deployed behavior cannot drift. (The deployed app doesn't actually
  need the key for the snapshot-restore path, but keeping it configured
  lets `scripts/fetch_data.py` and the Methodology/API-status code paths
  work identically in both places.)

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
  bootstrap.py   live-fetch bootstrap (currently unusable on the free tier — see above)
data_snapshot/   committed, dated dataset the deployed app restores from on first boot
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

* **The dataset is a frozen snapshot (as of 2026-08-24), not live.** NGX
  Pulse rebranded to Kobo Terminal and closed its free tier's
  historical-data loophole on or before 2026-09-16 (now `403 Starter plan
  required`, confirmed against the live API — see "Why this data no longer
  refreshes" above). The committed `data_snapshot/` is the last dataset
  fetched while the free tier still allowed it; nothing in it is
  fabricated or backfilled, it simply stops updating.
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
* No survivorship-bias handling: the universe is 2026-08-24's listings.

## References

Roll (1984), *J. Finance* 39(4) · Corwin & Schultz (2012), *J. Finance*
67(2) · Cleveland et al. (1990), *J. Official Statistics* 6(1).
