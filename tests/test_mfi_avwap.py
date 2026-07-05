"""Unit tests for Money Flow Index (MFI) and Anchored VWAP."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.volume import compute_mfi, mfi_state, compute_avwap
from techna.indicators.events import compute_events


def test_mfi_calculation():
    """Verify that Money Flow Index calculations are correct."""
    dates = pd.date_range("2026-01-01", periods=20)
    
    # Rising typical prices to establish high PMF, zero NMF
    high = [10.0 + i for i in range(20)]
    low = [8.0 + i for i in range(20)]
    close = [9.0 + i for i in range(20)]
    volume = [1000] * 20
    
    df = pd.DataFrame({
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)
    
    mfi = compute_mfi(df, period=14)
    
    # The first 14 bars (indices 0 to 13) should be NaN
    assert pd.isna(mfi.iloc[12])
    # nmf_sum should be 0 because typical price is strictly rising every day
    # So MFI should be 100.0 starting at index 14 (15th bar)
    assert mfi.iloc[14] == 100.0


def test_mfi_state():
    """Verify classification of MFI values."""
    assert mfi_state(85.0) == "overbought"
    assert mfi_state(15.0) == "oversold"
    assert mfi_state(50.0) == "neutral"
    assert mfi_state(float("nan")) == "neutral"


def test_compute_avwap():
    """Verify that Anchored VWAP calculations correctly anchor at a specific index."""
    dates = pd.date_range("2026-01-01", periods=10)
    
    # Flat price
    df = pd.DataFrame({
        "High": [110.0] * 10,
        "Low": [90.0] * 10,
        "Close": [100.0] * 10,
        "Volume": [1000] * 10,
    }, index=dates)
    
    # Typical price = (110 + 90 + 100) / 3 = 100.0
    # Anchored at index 5
    avwap = compute_avwap(df, anchor_idx=5)
    
    assert pd.isna(avwap.iloc[4])
    assert avwap.iloc[5] == pytest.approx(100.0)
    assert avwap.iloc[9] == pytest.approx(100.0)


def test_mfi_zone_entry_events():
    """Verify MFI zone entry triggers."""
    dates = pd.date_range("2026-01-01", periods=5)
    
    # 1. Overbought entry (crosses 80 from below)
    context1 = {
        "volume": {
            "_mfi_series": pd.Series([50.0, 60.0, 75.0, 78.0, 82.0], index=dates)
        }
    }
    ev1 = compute_events(context1)
    assert len(ev1) == 1
    assert ev1[0]["type"] == "mfi_zone_entry"
    assert "overbought" in ev1[0]["detail"]
    
    # 2. Oversold entry (crosses 20 from above)
    context2 = {
        "volume": {
            "_mfi_series": pd.Series([50.0, 40.0, 30.0, 22.0, 18.0], index=dates)
        }
    }
    ev2 = compute_events(context2)
    assert len(ev2) == 1
    assert ev2[0]["type"] == "mfi_zone_entry"
    assert "oversold" in ev2[0]["detail"]
