"""Unit and integration tests for the Weekly Volume Profile indicator."""
from __future__ import annotations

import pandas as pd

from techna.indicators.volume_profile_weekly import compute_volume_profile_weekly


def test_weekly_volume_profile_resampling_and_calculation():
    """Verify compute_volume_profile_weekly resamples to weekly and calculates correctly."""
    # Generate 30 weeks of daily prices (210 bars)
    dates = pd.date_range("2026-01-01", periods=210)
    
    # Flat price around 100.0, but with a spike to 120 and drop to 80 to establish high/low range
    close = [100.0] * 210
    high = [101.0] * 210
    low = [99.0] * 210
    volume = [1000] * 210
    
    # Create distinct spikes to verify distribution
    high[50] = 120.0
    low[150] = 80.0
    close[-1] = 115.0  # Daily close is high, above the usual weekly range
    
    df = pd.DataFrame({
        "Open": [100.0] * 210,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)
    
    # Calculate weekly volume profile (using lookback_weeks=10 to check warning/used bars)
    res = compute_volume_profile_weekly(df, lookback_weeks=10, bins=5, value_area=0.70)
    
    assert res["status"] == "ok"
    assert res["weeks_used"] == 10
    assert res["state_weekly"] == "above"  # 115.0 is above VAH which will be around ~101.0
    assert len(res["bins"]) == 6
    assert len(res["volumes"]) == 5


def test_weekly_volume_profile_short_history_warning():
    """Verify warning is issued when history is shorter than lookback_weeks."""
    # 3 weeks of daily prices
    dates = pd.date_range("2026-01-01", periods=21)
    df = pd.DataFrame({
        "Open": [100.0] * 21,
        "High": [101.0] * 21,
        "Low": [99.0] * 21,
        "Close": [100.0] * 21,
        "Volume": [1000] * 21,
    }, index=dates)
    
    res = compute_volume_profile_weekly(df, lookback_weeks=52, bins=10)
    
    assert res["status"] == "warning"
    assert "Insufficient history" in res["warning"]
    assert res["weeks_used"] == 4
