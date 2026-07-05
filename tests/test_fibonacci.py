"""Unit tests for the Fibonacci Retracement indicator and respect statistics."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.fibonacci import compute_fibonacci


def test_fibonacci_upward_swing():
    """Verify Fibonacci calculations for an upward swing (low before high)."""
    # 20 bars of daily data
    dates = pd.date_range("2026-01-01", periods=20)
    
    close = [100.0] * 20
    high = [105.0] * 20
    low = [95.0] * 20
    
    # Establish swing low at index 5 and swing high at index 15
    low[5] = 50.0   # swing low = 50
    high[15] = 150.0 # swing high = 150
    
    df = pd.DataFrame({
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": [1000] * 20,
    }, index=dates)
    
    res = compute_fibonacci(df, lookback=20, levels=[0.382, 0.5])
    
    assert res["status"] == "ok"
    assert res["swing_low"] == 50.0
    assert res["swing_high"] == 150.0
    assert res["direction"] == "up"
    
    # Retracement levels from top to bottom (swing_high - level * range)
    # 0.382 level: 150 - 0.382 * 100 = 111.8
    # 0.5 level: 150 - 0.5 * 100 = 100.0
    assert res["levels"][0.382] == pytest.approx(111.8)
    assert res["levels"][0.5] == pytest.approx(100.0)


def test_fibonacci_downward_swing():
    """Verify Fibonacci calculations for a downward swing (high before low)."""
    dates = pd.date_range("2026-01-01", periods=20)
    
    close = [100.0] * 20
    high = [105.0] * 20
    low = [95.0] * 20
    
    # Establish swing high at index 5 and swing low at index 15
    high[5] = 150.0  # swing high = 150
    low[15] = 50.0   # swing low = 50
    
    df = pd.DataFrame({
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": [1000] * 20,
    }, index=dates)
    
    res = compute_fibonacci(df, lookback=20, levels=[0.382, 0.5])
    
    assert res["status"] == "ok"
    assert res["swing_low"] == 50.0
    assert res["swing_high"] == 150.0
    assert res["direction"] == "down"
    
    # Retracement levels from bottom to top (swing_low + level * range)
    # 0.382 level: 50 + 0.382 * 100 = 88.2
    # 0.5 level: 50 + 0.5 * 100 = 100.0
    assert res["levels"][0.382] == pytest.approx(88.2)
    assert res["levels"][0.5] == pytest.approx(100.0)


def test_fibonacci_insufficient_history_warning():
    """Verify Fibonacci warns when data length is less than lookback."""
    dates = pd.date_range("2026-01-01", periods=10)
    df = pd.DataFrame({
        "High": [105.0] * 10,
        "Low": [95.0] * 10,
        "Close": [100.0] * 10,
        "Volume": [1000] * 10,
    }, index=dates)
    
    res = compute_fibonacci(df, lookback=20)
    assert res["status"] == "warning"
    assert "Insufficient history" in res["warning"]
