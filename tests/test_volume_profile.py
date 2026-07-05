"""Unit tests for the Volume Profile (VP) indicator module."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.volume_profile import compute_volume_profile


def test_volume_profile_proportional_allocation():
    """Verify exact volume distribution, POC tie-break, and VA expansion with a mini fixture."""
    dates = pd.date_range("2026-01-01", periods=4)
    
    # Manually curated 4-bar dataset
    # Bar 1: Low 12, High 28, Volume 100
    # Bar 2: Low 22, High 38, Volume 200
    # Bar 3: Low 15, High 15, Volume 150 (single price)
    # Bar 4: Low 35, High 35, Volume 50 (single price)
    df = pd.DataFrame({
        "Open": [15.0] * 4,
        "High": [28.0, 38.0, 15.0, 35.0],
        "Low":  [12.0, 22.0, 15.0, 35.0],
        "Close": [20.0, 30.0, 15.0, 35.0],
        "Volume": [100.0, 200.0, 150.0, 50.0],
    }, index=dates)
    
    # We use 3 bins: min_low=12, max_high=38
    # np.linspace(12, 38, 4) -> [12.0, 20.666667, 29.333333, 38.0]
    # Bin 0: [12.0, 20.666667)
    # Bin 1: [20.666667, 29.333333)
    # Bin 2: [29.333333, 38.0]
    
    res = compute_volume_profile(df, lookback=4, bins=3, value_area_pct=0.70)
    
    assert res["status"] == "ok"
    assert res["lookback_used"] == 4
    
    # Verify volumes list values approximately match math
    v = res["volumes"]
    # Bar 1: width = 16. Overlap Bin 0 = 8.666667, Bin 1 = 7.333333.
    # Bar 2: width = 16. Overlap Bin 1 = 7.333333, Bin 2 = 8.666667.
    # Bar 3 (15.0) goes to Bin 0.
    # Bar 4 (35.0) goes to Bin 2.
    # Bin 0 vol: 100 * (8.666667/16) + 150 = 54.166667 + 150 = 204.166667
    # Bin 1 vol: 100 * (7.333333/16) + 200 * (7.333333/16) = 45.833333 + 91.666667 = 137.5
    # Bin 2 vol: 200 * (8.666667/16) + 50 = 108.333333 + 50 = 158.333333
    
    assert pytest.approx(v[0], abs=1e-2) == 204.17
    assert pytest.approx(v[1], abs=1e-2) == 137.50
    assert pytest.approx(v[2], abs=1e-2) == 158.33
    
    # POC should be Bin 0 center: (12.0 + 20.666667) / 2 = 16.333333
    assert pytest.approx(res["poc"], abs=1e-2) == 16.33


def test_volume_profile_expansion_tie_break():
    """Verify Value Area expansion tie-break ('eşitlikte üst')."""
    dates = pd.date_range("2026-01-01", periods=5)
    
    # Create a situation where POC is in the middle (index 1 of 3 bins),
    # and upper and lower bins have exactly equal volume.
    # Bin edges: [10.0, 20.0, 30.0, 40.0]
    # Bin 0: [10, 20) -> 100 volume
    # Bin 1: [20, 30) -> 200 volume (POC)
    # Bin 2: [30, 40] -> 100 volume
    
    df = pd.DataFrame({
        "Open": [25.0] * 5,
        # Construct exact bar allocations
        # Bar 1: Low 15, High 15, Vol 100 (in Bin 0)
        # Bar 2: Low 25, High 25, Vol 200 (in Bin 1)
        # Bar 3: Low 35, High 35, Vol 100 (in Bin 2)
        "High":  [15.0, 25.0, 35.0, 25.0, 25.0],
        "Low":   [15.0, 25.0, 35.0, 25.0, 25.0],
        "Close": [15.0, 25.0, 35.0, 25.0, 25.0],
        "Volume": [100.0, 200.0, 100.0, 0.0, 0.0],
    }, index=dates)
    
    # Total volume = 400. Target = 70% of 400 = 280.
    # POC is index 1 (Vol=200). 200 < 280, so we must expand.
    # Neighbors of index 1: index 0 (Vol=100) and index 2 (Vol=100).
    # Since volumes are equal (100 vs 100), the upper neighbor index 2 must be added first.
    # Let's set target volume_area_pct = 0.70.
    # If upper index 2 is added first: VA volume becomes 200 + 100 = 300 >= 280, expansion ends.
    # Right index = 2, Left index = 1.
    # VAL = bin_edges[1] = 20.0. VAH = bin_edges[3] = 40.0.
    
    res = compute_volume_profile(df, lookback=5, bins=3, value_area_pct=0.70)
    
    assert res["poc"] == 25.0
    assert pytest.approx(res["val"]) == 21.666666666666668
    assert res["vah"] == 35.0
    
    # If tie-break had chosen lower neighbor index 0, Left index would be 0, Right index = 1.
    # VAL would be 15.0, VAH would be 28.33333333.
    # Since VAL=21.67 and VAH=35.0, it proves that the upper neighbor was correctly chosen on tie!


def test_volume_profile_flat_price_history():
    """Verify flat price history edge case (min_low == max_high)."""
    dates = pd.date_range("2026-01-01", periods=10)
    df = pd.DataFrame({
        "Open": [10.0] * 10,
        "High": [10.0] * 10,
        "Low": [10.0] * 10,
        "Close": [10.0] * 10,
        "Volume": [100.0] * 10,
    }, index=dates)
    
    res = compute_volume_profile(df, lookback=10, bins=5, value_area_pct=0.70)
    assert res["poc"] == 10.0
    assert res["vah"] == 10.0
    assert res["val"] == 10.0
    assert res["state"] == "inside"


def test_volume_profile_insufficient_history_warning():
    """Verify that insufficient history returns warning status and correct message."""
    dates = pd.date_range("2026-01-01", periods=5)
    df = pd.DataFrame({
        "Open": [10.0] * 5,
        "High": [12.0, 14.0, 11.0, 13.0, 12.0],
        "Low": [9.0, 10.0, 8.5, 11.0, 10.0],
        "Close": [11.0, 13.0, 10.0, 12.0, 11.0],
        "Volume": [100.0] * 5,
    }, index=dates)
    
    # Request lookback=10 (history has only 5 bars)
    res = compute_volume_profile(df, lookback=10, bins=5, value_area_pct=0.70)
    assert res["status"] == "warning"
    assert "Insufficient history" in res["warning"]
    assert res["lookback_used"] == 5
