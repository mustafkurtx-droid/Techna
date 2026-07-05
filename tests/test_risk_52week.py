"""Offline tests for 52-week range position indicator (validates risk_52week.feature)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna.indicators.risk_context import compute_52week_range


def test_52week_range_accuracy():
    """Scenario: Calculate position percent and verify state classification near boundaries."""
    # 52w range: min=50.0, max=150.0, rng=100.0
    close = pd.Series([100.0, 50.0, 150.0, 140.0]) # current = 140.0
    # Expected position: (140.0 - 50.0) / 100.0 * 100 = 90.0% -> near_52w_high
    res = compute_52week_range(close, window=4)
    assert res["high"] == 150.0
    assert res["low"] == 50.0
    assert res["current"] == 140.0
    assert res["position_pct"] == pytest.approx(90.0)
    assert res["state"] == "near_52w_high"
    
    # Near low: current = 60.0 -> position_pct = 10.0% -> near_52w_low
    close_low = pd.Series([100.0, 50.0, 150.0, 60.0])
    res_low = compute_52week_range(close_low, window=4)
    assert res_low["position_pct"] == pytest.approx(10.0)
    assert res_low["state"] == "near_52w_low"
    
    # Mid range: current = 100.0 -> position_pct = 50.0% -> mid_range
    close_mid = pd.Series([100.0, 50.0, 150.0, 100.0])
    res_mid = compute_52week_range(close_mid, window=4)
    assert res_mid["position_pct"] == pytest.approx(50.0)
    assert res_mid["state"] == "mid_range"
    
    # Flat series: min = max = 100.0 -> position_pct is NaN -> mid_range
    close_flat = pd.Series([100.0, 100.0, 100.0, 100.0])
    res_flat = compute_52week_range(close_flat, window=4)
    assert np.isnan(res_flat["position_pct"])
    assert res_flat["state"] == "mid_range"
