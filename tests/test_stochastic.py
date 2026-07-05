"""Unit tests for the Stochastic Oscillator indicator and daily events."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.momentum import compute_stochastic
from techna.indicators.events import compute_events


def test_stochastic_calculation():
    """Verify that slow stochastic %K and %D calculations are numerically accurate."""
    dates = pd.date_range("2026-01-01", periods=20)
    
    # 20 bars of data
    df = pd.DataFrame({
        "High": [110.0] * 20,
        "Low": [90.0] * 20,
        "Close": [100.0] * 20,
        "Volume": [1000] * 20,
    }, index=dates)
    
    res = compute_stochastic(df, k_period=14, smooth_k=3, d_period=3)
    
    # All values are exactly in the middle of 90-110 range: (100-90)/(110-90) = 50%
    # So raw_k = 50.0. After smooth (SMA of 50.0), slow_k = 50.0, slow_d = 50.0.
    # The first 14+3-1 = 16 bars for slow_k should be NaN.
    # The first 14+3-1+3-1 = 18 bars for slow_d should be NaN.
    
    assert pd.isna(res["slow_k"].iloc[14])
    assert res["slow_k"].iloc[15] == pytest.approx(50.0)
    assert pd.isna(res["slow_d"].iloc[16])
    assert res["slow_d"].iloc[17] == pytest.approx(50.0)
    
    # Test division by zero: High == Low
    df_flat = pd.DataFrame({
        "High": [100.0] * 20,
        "Low": [100.0] * 20,
        "Close": [100.0] * 20,
    }, index=dates)
    res_flat = compute_stochastic(df_flat, k_period=14)
    # raw_k should be NaN, and thus slow_k/d should be NaN
    assert pd.isna(res_flat["slow_k"].iloc[19])


def test_stochastic_zone_entry_events():
    """Verify Stochastic slow_k zone entry triggers."""
    dates = pd.date_range("2026-01-01", periods=5)
    
    # 1. Enter Overbought: crosses 80 from below
    context1 = {
        "stochastic": {
            "status": "ok",
            "_slow_k_series": pd.Series([50.0, 60.0, 75.0, 78.0, 82.0], index=dates)
        }
    }
    ev1 = compute_events(context1)
    assert len(ev1) == 1
    assert ev1[0]["type"] == "stoch_zone_entry"
    assert ev1[0]["direction"] == "neutral"
    assert "overbought" in ev1[0]["detail"]
    
    # 2. Enter Oversold: crosses 20 from above
    context2 = {
        "stochastic": {
            "status": "ok",
            "_slow_k_series": pd.Series([50.0, 40.0, 25.0, 22.0, 18.0], index=dates)
        }
    }
    ev2 = compute_events(context2)
    assert len(ev2) == 1
    assert ev2[0]["type"] == "stoch_zone_entry"
    assert ev2[0]["direction"] == "neutral"
    assert "oversold" in ev2[0]["detail"]
    
    # 3. No transition on last bar
    context3 = {
        "stochastic": {
            "status": "ok",
            "_slow_k_series": pd.Series([50.0, 40.0, 25.0, 18.0, 15.0], index=dates)
        }
    }
    ev3 = compute_events(context3)
    assert len(ev3) == 0
