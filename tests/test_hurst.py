"""Offline tests for Hurst Exponent analysis (validates specs/hurst.feature)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna.indicators.econometrics import compute_hurst_analysis, compute_hurst_exponent


@pytest.fixture
def persistent_series():
    """Generates a strongly persistent trending series with a fixed seed."""
    rs = np.random.RandomState(42)
    # Autocorrelated steps to build strong persistence
    steps = np.zeros(300)
    steps[0] = rs.normal()
    for i in range(1, 300):
        steps[i] = 0.8 * steps[i-1] + rs.normal(scale=0.5)
    trend = np.arange(300) * 0.2
    series_val = trend + steps
    return pd.Series(series_val, index=pd.date_range("2026-01-01", periods=300, freq="D"))


@pytest.fixture
def mean_reverting_series():
    """Generates a strongly mean-reverting series with a fixed seed."""
    rs = np.random.RandomState(42)
    n = 300
    # Negative autocorrelation for strong mean reversion
    steps = np.zeros(n)
    steps[0] = rs.normal()
    for i in range(1, n):
        steps[i] = -0.7 * steps[i-1] + rs.normal(scale=0.5)
    return pd.Series(steps, index=pd.date_range("2026-01-01", periods=n, freq="D"))


@pytest.fixture
def clustered_volatility_series():
    """Generates a series with volatility clustering (GARCH-like process)."""
    rs = np.random.RandomState(42)
    n = 300
    h = np.zeros(n)
    r = np.zeros(n)
    h[0] = 1.0
    for t in range(1, n):
        # High persistence (beta1 = 0.85) ensures volatility has long memory
        h[t] = 0.1 + 0.10 * (r[t-1]**2) + 0.85 * h[t-1]
        r[t] = rs.normal(loc=0.0, scale=np.sqrt(h[t]))
    return pd.Series(r, index=pd.date_range("2026-01-01", periods=n, freq="D"))


def test_hurst_persistent_series(persistent_series):
    """Verify that a persistent trending series yields H > 0.55."""
    res = compute_hurst_exponent(persistent_series)
    assert res["hurst"] > 0.55
    assert res["state_label"] == "persistent_trending"


def test_hurst_mean_reverting_series(mean_reverting_series):
    """Verify that a mean-reverting series yields H < 0.45."""
    res = compute_hurst_exponent(mean_reverting_series)
    assert res["hurst"] < 0.45
    assert res["state_label"] == "mean_reverting"


def test_hurst_volatility_long_memory(clustered_volatility_series):
    """Verify that volatility (squared returns) has longer memory than returns."""
    res = compute_hurst_analysis(clustered_volatility_series)
    
    returns_h = res["returns"]["hurst"]
    volatility_h = res["volatility"]["hurst"]
    
    # Volatility should exhibit longer memory (higher Hurst) due to clustering
    assert volatility_h > returns_h
