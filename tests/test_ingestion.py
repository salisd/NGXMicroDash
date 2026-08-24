import pandas as pd
import pytest

from ngxdash.ingestion.base import SourceDataError, normalize_ohlcv


def test_normalizes_eodhd_style_records():
    records = [
        {"date": "2024-01-02", "open": 10, "high": 11, "low": 9.5, "close": 10.5, "volume": 1000},
        {"date": "2024-01-03", "open": 10.5, "high": 10.8, "low": 10.1, "close": 10.2, "volume": 500},
    ]
    df = normalize_ohlcv(records, "test", "ABC")
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.name == "date"
    assert len(df) == 2
    assert df["close"].iloc[0] == 10.5


def test_missing_high_low_kept_as_nan_not_fabricated():
    records = [
        {"trade_date": "2024-01-02", "close_price": 10.5, "volume": 1000},
        {"trade_date": "2024-01-03", "close_price": 10.2, "volume": 500},
    ]
    df = normalize_ohlcv(records, "test", "ABC")
    assert df["high"].isna().all() and df["low"].isna().all()
    assert df["close"].notna().all()


def test_snapshot_response_raises():
    with pytest.raises(SourceDataError, match="snapshot"):
        normalize_ohlcv(
            [{"symbol": "ABC", "current_price": 10.5, "volume": 1}], "test", "ABC"
        )


def test_single_row_history_raises():
    with pytest.raises(SourceDataError):
        normalize_ohlcv([{"date": "2024-01-02", "close": 10.5}], "test", "ABC")


def test_duplicate_dates_deduplicated_keep_last():
    records = [
        {"date": "2024-01-02", "close": 10.0},
        {"date": "2024-01-02", "close": 10.5},
        {"date": "2024-01-03", "close": 10.2},
    ]
    df = normalize_ohlcv(records, "test", "ABC")
    assert len(df) == 2
    assert df["close"].iloc[0] == 10.5
