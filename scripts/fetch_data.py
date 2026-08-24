#!/usr/bin/env python3
"""Populate the local cache with NGX universe + daily OHLCV history.

Usage:
    python scripts/fetch_data.py                    # auto-pick source from env keys
    python scripts/fetch_data.py --source eodhd
    python scripts/fetch_data.py --symbols GTCO,DANGCEM --start 2017-01-01
    python scripts/fetch_data.py --refresh-universe # re-pull sector table only

The script is incremental: symbols already in the cache are skipped unless
--force. That makes tight free-tier rate limits workable — run it on
consecutive days until coverage is complete.
"""

import argparse
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from ngxdash import config
from ngxdash.ingestion import cache
from ngxdash.ingestion.base import SourceDataError
from ngxdash.ingestion.eodhd import EODHDSource
from ngxdash.ingestion.ngx_doclib import fetch_universe, select_universe
from ngxdash.ingestion.ngx_pulse import NGXPulseSource


def build_source(name: str):
    if name == "ngxpulse":
        return NGXPulseSource(config.NGX_PULSE_API_KEY), 6.5  # 10 req/min limit
    if name == "eodhd":
        return EODHDSource(config.EODHD_API_TOKEN), 1.0
    raise SystemExit(f"unknown source: {name}")


def auto_source() -> str:
    if config.NGX_PULSE_API_KEY:
        return "ngxpulse"
    if config.EODHD_API_TOKEN:
        return "eodhd"
    raise SystemExit(
        "No API key found. Set NGX_PULSE_API_KEY or EODHD_API_TOKEN in the "
        "environment or a .env file (see .env.example)."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["ngxpulse", "eodhd"], default=None)
    ap.add_argument("--symbols", help="comma-separated override of the default universe")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--sectors", default=",".join(config.DEFAULT_SECTORS))
    ap.add_argument("--per-sector", type=int, default=config.DEFAULT_SYMBOLS_PER_SECTOR)
    ap.add_argument("--force", action="store_true", help="re-fetch cached symbols")
    ap.add_argument("--refresh-universe", action="store_true")
    ap.add_argument("--max-symbols", type=int, default=None,
                    help="stop after N fetches (useful on 20/day free tiers)")
    args = ap.parse_args()

    print("Fetching NGX universe/sector table (public doclib API)...")
    universe = fetch_universe()
    cache.save_universe(universe)
    print(f"  {len(universe)} listed equities, "
          f"{universe['sector'].nunique()} sectors -> {config.UNIVERSE_PATH}")
    if args.refresh_universe:
        return 0

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    else:
        selected = select_universe(
            universe, [s.strip().upper() for s in args.sectors.split(",")], args.per_sector
        )
        symbols = selected["symbol"].tolist()
        print(f"Selected {len(symbols)} symbols across "
              f"{selected['sector'].nunique()} sectors (top {args.per_sector} "
              "by traded value each).")

    source_name = args.source or auto_source()
    source, delay = build_source(source_name)
    print(f"Source: {source_name}  (inter-request delay {delay}s)")

    done = failed = skipped = 0
    for sym in symbols:
        if args.max_symbols is not None and done >= args.max_symbols:
            print(f"Reached --max-symbols={args.max_symbols}; stopping. "
                  "Re-run later to continue (cached symbols are skipped).")
            break
        if not args.force and cache.load_prices(sym) is not None:
            skipped += 1
            continue
        try:
            df = source.fetch_history(sym, start=args.start, end=args.end)
        except SourceDataError as e:
            print(f"  {sym}: FAILED — {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001 — keep going through the list
            print(f"  {sym}: FAILED — {type(e).__name__}: {e}")
            failed += 1
        else:
            cache.save_prices(sym, df, source_name)
            hl = "OHLCV" if df["high"].notna().any() else "close/volume only"
            print(f"  {sym}: {len(df)} rows {df.index.min().date()} → "
                  f"{df.index.max().date()} ({hl})")
            done += 1
        time.sleep(delay)

    print(f"\nDone: {done} fetched, {skipped} already cached, {failed} failed.")
    cov = cache.coverage_summary()
    if not cov.empty:
        print("\nCoverage:")
        print(cov.to_string(index=False))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
