"""Offline tests for Stationarity Analysis (ADF + KPSS)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna.indicators.econometrics import (
    compute_stationarity_tests,
    stationarity_verdict,
)


@pytest.fixture
def random_walk_series():
    """Generates a non-stationary random walk series with a fixed seed."""
    rs = np.random.RandomState(42)
    steps = rs.normal(loc=0.0, scale=1.0, size=200)
    # Random walk: cumulative sum
    series_val = steps.cumsum()
    return pd.Series(series_val, index=pd.date_range("2026-01-01", periods=200, freq="D"))


@pytest.fixture
def stationary_series():
    """Generates a stationary AR(1) mean-reverting series with a fixed seed."""
    rs = np.random.RandomState(42)
    n = 200
    phi = 0.3
    vals = np.zeros(n)
    for i in range(1, n):
        vals[i] = phi * vals[i-1] + rs.normal(loc=0.0, scale=1.0)
    return pd.Series(vals, index=pd.date_range("2026-01-01", periods=200, freq="D"))


def test_stationarity_on_random_walk(random_walk_series):
    """Verify that a random walk is identified as non-stationary."""
    res = compute_stationarity_tests(random_walk_series, regression="c")
    
    # Random walk: adf decision is typically "fail to reject" (has unit root)
    # kpss decision is typically "reject H0" (not stationary)
    assert res["adf"]["decision"] == "fail to reject"
    assert res["kpss"]["decision"] == "reject H0"
    assert res["state_label"] == "non-stationary (unit root / random walk)"


def test_stationarity_on_stationary_ar1(stationary_series):
    """Verify that an AR(1) mean-reverting series is identified as stationary."""
    res = compute_stationarity_tests(stationary_series, regression="c")
    
    # AR(1) phi=0.3: adf rejects H0 (stationary)
    # kpss fails to reject H0 (stationary)
    assert res["adf"]["decision"] == "reject H0"
    assert res["kpss"]["decision"] == "fail to reject"
    assert res["state_label"] == "stationary"


def test_combined_verdict_all_four_branches():
    """All four ADF/KPSS decision combinations map to the correct label."""
    R, F = "reject H0", "fail to reject"
    assert stationarity_verdict(R, F) == "stationary"
    assert stationarity_verdict(F, R) == "non-stationary (unit root / random walk)"
    assert stationarity_verdict(R, R) == "difference-stationary / possibly fractional"
    assert stationarity_verdict(F, F) == "inconclusive / trend-stationary"


def test_combined_verdict_decision_rules():
    """Verify combined verdict decision matrix with mocked series outputs."""
    # We can test the verdict logic by supplying mock series or verifying the output structure.
    # To test the return structure for small datasets:
    small_series = pd.Series(np.arange(5))
    res_small = compute_stationarity_tests(small_series)
    assert res_small["state_label"] == "inconclusive / trend-stationary"
    assert res_small["adf"]["pvalue"] == 1.0
    assert res_small["kpss"]["pvalue"] == 1.0
