"""Central configuration: paths, environment keys, default parameters."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("NGXDASH_DATA_DIR", PROJECT_ROOT / "data"))
PRICES_DIR = DATA_DIR / "prices"
UNIVERSE_PATH = DATA_DIR / "universe.parquet"
META_PATH = DATA_DIR / "meta.json"

NGX_PULSE_API_KEY = os.environ.get("NGX_PULSE_API_KEY", "")
EODHD_API_TOKEN = os.environ.get("EODHD_API_TOKEN", "")

# Default analysis parameters (all overridable in the dashboard UI).
DEFAULT_ROLL_WINDOW = 60        # trading days for rolling Roll covariance
DEFAULT_CS_WINDOW = 21          # trading days for averaging 2-day CS estimates
DEFAULT_RV_WINDOW = 21          # trading days for realized volatility
TRADING_DAYS_PER_YEAR = 252
STL_PERIOD = 5                  # trading-week seasonality for daily volume

# Sectors targeted by the default fetch (official NGX classification names).
DEFAULT_SECTORS = [
    "FINANCIAL SERVICES",
    "CONSUMER GOODS",
    "INDUSTRIAL GOODS",
    "OIL AND GAS",
    "ICT",
    "AGRICULTURE",
]
# Number of most-actively-traded symbols to take per sector.
DEFAULT_SYMBOLS_PER_SECTOR = 6
