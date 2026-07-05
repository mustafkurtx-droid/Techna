"""Offline tests for liquidity metrics and classification (validates risk_liquidity.feature)."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.risk_context import compute_liquidity_metrics


def test_liquidity_classification():
    """Scenario: Verify average traded value and thresholds mapping."""
    volume = pd.Series([1000.0] * 20)
    close = pd.Series([5000.0] * 20)
    # Traded value: 1000 * 5000 = 5,000,000 (threshold: moderate_liquidity)
    res_mod = compute_liquidity_metrics(volume, close)
    assert res_mod["avg_value_20"] == pytest.approx(5_000_000.0)
    assert res_mod["state"] == "moderate_liquidity"
    
    # High liquidity: traded value 55,000,000
    close_high = pd.Series([55000.0] * 20)
    res_high = compute_liquidity_metrics(volume, close_high)
    assert res_high["avg_value_20"] == pytest.approx(55_000_000.0)
    assert res_high["state"] == "high_liquidity"
    
    # Low liquidity: traded value 4,500,000
    close_low = pd.Series([4500.0] * 20)
    res_low = compute_liquidity_metrics(volume, close_low)
    assert res_low["avg_value_20"] == pytest.approx(4_500_000.0)
    assert res_low["state"] == "low_liquidity"
