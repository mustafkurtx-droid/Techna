"""Offline tests for systematic risk Beta indicator (validates risk_beta.feature)."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.risk_context import compute_beta


def test_beta_calculation_accuracy():
    """Scenario: Calculate Beta, Alpha, R-Squared against manually calculated covariance."""
    # Let's create a returns series where stock is exactly 2 * benchmark
    # stock: [0.02, -0.01, 0.04, -0.02]
    # bench: [0.01, -0.005, 0.02, -0.01]
    bench = pd.Series([0.01, -0.005, 0.02, -0.01])
    stock = 2.0 * bench
    
    res = compute_beta(stock, bench)
    
    # Expected beta = 2.0, R-squared = 1.0, Alpha_annualized = 0.0 (since mean_s = 2*mean_b)
    assert res["beta"] == pytest.approx(2.0)
    assert res["r_squared"] == pytest.approx(1.0)
    assert res["alpha_annualized"] == pytest.approx(0.0, abs=1e-7)
    assert res["state"] == "high_beta"
    
    # Low beta: stock = 0.5 * bench
    stock_low = 0.5 * bench
    res_low = compute_beta(stock_low, bench)
    assert res_low["beta"] == pytest.approx(0.5)
    assert res_low["state"] == "low_beta"
    
    # Market beta: stock = 1.0 * bench
    stock_mkt = 1.0 * bench
    res_mkt = compute_beta(stock_mkt, bench)
    assert res_mkt["beta"] == pytest.approx(1.0)
    assert res_mkt["state"] == "market_beta"
