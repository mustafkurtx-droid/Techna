"""Unit and integration tests for the Volatility Squeeze indicator and daily events."""
from __future__ import annotations

import pandas as pd

from techna.indicators.squeeze import compute_squeeze
from techna.indicators.events import compute_events


def test_squeeze_duration_counting():
    """Verify that compute_squeeze accurately counts consecutive active squeeze bars."""
    dates = pd.date_range("2026-01-01", periods=30)
    
    # Construct a series where:
    # Bollinger Bands (standard dev) is very small (flat prices = 100.0) -> squeeze active.
    # We make prices flat for the last 5 bars to make squeeze active,
    # and have high volatility before that to make squeeze inactive.
    
    close = [100.0] * 30
    high = [101.0] * 30
    low = [99.0] * 30
    volume = [1000] * 30
    
    # Before index 25, we introduce high volatility to break the squeeze:
    # At index 24 (6 bars ago), high = 150, low = 50. Bollinger Bands will expand way outside Keltner Channels.
    # Let's override those:
    for idx in range(25):
        if idx % 2 == 0:
            close[idx] = 115.0
            high[idx] = 130.0
            low[idx] = 90.0
        else:
            close[idx] = 85.0
            high[idx] = 110.0
            low[idx] = 70.0
            
    df = pd.DataFrame({
        "Open": [100.0] * 30,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)
    
    res = compute_squeeze(df, period=10, bb_mult=1.0, kc_mult=2.0)
    
    assert res["status"] == "ok"
    assert res["squeeze_active"] is True
    # The last 5 bars (indices 25, 26, 27, 28, 29) are completely flat,
    # so standard deviation is 0. Bollinger Bands width is 0.
    # ATR is non-zero, so Keltner Channels width is > 0.
    # Therefore, Bollinger bands are inside Keltner channels (squeeze active).
    # The duration should be at least 5 bars.
    assert res["squeeze_duration"] >= 5


def test_squeeze_events():
    """Verify squeeze_start and squeeze_release daily event triggers."""
    dates = pd.date_range("2026-01-01", periods=5)
    
    # 1. Squeeze Start: False -> True on last bar
    # We mock _squeeze_active_series
    context1 = {
        "squeeze": {
            "status": "ok",
            "_squeeze_active_series": pd.Series([False, False, False, False, True], index=dates)
        }
    }
    ev1 = compute_events(context1)
    assert len(ev1) == 1
    assert ev1[0]["type"] == "squeeze_start"
    assert ev1[0]["direction"] == "neutral"
    assert "Squeeze activated" in ev1[0]["detail"]
    
    # 2. Squeeze Release: True -> False on last bar
    context2 = {
        "squeeze": {
            "status": "ok",
            "_squeeze_active_series": pd.Series([True, True, True, True, False], index=dates)
        }
    }
    ev2 = compute_events(context2)
    assert len(ev2) == 1
    assert ev2[0]["type"] == "squeeze_release"
    assert ev2[0]["direction"] == "neutral"
    assert "Squeeze released" in ev2[0]["detail"]
