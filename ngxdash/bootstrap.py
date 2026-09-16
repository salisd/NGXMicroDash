"""Live data bootstrap: populate an empty cache from the primary API.

STATUS (2026-09-16): not currently usable for a from-empty deployment
bootstrap. NGX Pulse rebranded to Kobo Terminal and its free tier now caps
history at 7 days (previously ambiguous, now explicitly enforced) — too
short for any estimator window here. The deployed app restores a bundled
snapshot instead (see ngxdash.ingestion.cache.restore_from_snapshot and
app/common.py::ensure_data). This module is kept because the logic is
correct and becomes usable again on a paid tier, or manually via
scripts/fetch_data.py for topping up whatever the free tier's 7-day window
still allows.

Used by the Streamlit app when it starts with no local cache (e.g. a fresh
Streamlit Cloud container, whose filesystem is ephemeral). Deliberately
reuses the same source clients and cache layer as scripts/fetch_data.py so
there is one fetch implementation to keep correct.

Rate limiting: NGX Pulse Personal tier allows 10 requests/min and 100/day.
The inter-request delay keeps us at ~9/min; one full bootstrap costs
1 (universe) + one call per symbol. Symbols are fetched most-traded first,
so if the daily budget runs out mid-boot the most liquid names are already
in the cache and the app renders partial coverage honestly.
"""

from collections.abc import Callable
import time

from . import config
from .ingestion import cache
from .ingestion.base import SourceDataError
from .ingestion.ngx_doclib import fetch_universe, select_universe
from .ingestion.ngx_pulse import NGXPulseSource

INTER_REQUEST_DELAY_S = 6.5  # ~9.2 req/min, under the 10/min Personal cap


def bootstrap_needed() -> bool:
    return not cache.cached_symbols()


def run_bootstrap(
    progress: Callable[[int, int, str], None] | None = None,
    start: str = "2015-01-01",
) -> dict:
    """Fetch universe + default-universe price history into the cache.

    progress(done, total, message) is called before each symbol fetch and
    once at the end. Returns {"fetched": n, "failed": [(symbol, reason)]}.
    Never raises for a single symbol's failure; raises only if the universe
    itself cannot be fetched (nothing sensible can render without it).
    """
    universe = fetch_universe()
    cache.save_universe(universe)
    selected = select_universe(
        universe, config.DEFAULT_SECTORS, config.DEFAULT_SYMBOLS_PER_SECTOR
    )
    # Most-traded first across the whole selection (see module docstring).
    symbols = (
        selected.sort_values("value_traded", ascending=False)["symbol"].tolist()
    )
    source = NGXPulseSource(config.NGX_PULSE_API_KEY)

    fetched, failed = 0, []
    total = len(symbols)
    for i, sym in enumerate(symbols):
        if progress:
            progress(i, total, f"Fetching {sym} ({i + 1}/{total})")
        try:
            df = source.fetch_history(sym, start=start)
        except SourceDataError as e:
            failed.append((sym, str(e)))
        except Exception as e:  # noqa: BLE001 — a flaky symbol must not kill boot
            failed.append((sym, f"{type(e).__name__}: {e}"))
        else:
            cache.save_prices(sym, df, "ngxpulse")
            fetched += 1
        if i < total - 1:
            time.sleep(INTER_REQUEST_DELAY_S)
    if progress:
        progress(total, total, f"Done: {fetched} fetched, {len(failed)} failed")
    return {"fetched": fetched, "failed": failed}
