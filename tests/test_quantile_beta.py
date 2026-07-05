"""Offline tests for Quantile Regression Beta Analysis (validates specs/quantile_beta.feature)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna.indicators.econometrics import compute_quantile_beta


@pytest.fixture
def symmetric_returns():
    """Generates returns with symmetric beta relationship (slope ~ 1.0)."""
    rs = np.random.RandomState(42)
    bench = rs.normal(loc=0.0, scale=1.0, size=250)
    # stock = 1.0 * bench + noise
    stock = 1.0 * bench + rs.normal(loc=0.0, scale=0.5, size=250)
    
    dates = pd.date_range("2026-01-01", periods=250, freq="D")
    return pd.Series(stock, index=dates, name="stock"), pd.Series(bench, index=dates, name="bench")


@pytest.fixture
def downside_sensitive_returns():
    """Generates returns where stock is highly sensitive to benchmark drops."""
    rs = np.random.RandomState(42)
    bench = rs.normal(loc=0.0, scale=1.0, size=250)
    
    stock = np.zeros(250)
    for i in range(250):
        if bench[i] < 0:
            stock[i] = 2.0 * bench[i] + rs.normal(scale=0.5)
        else:
            stock[i] = 0.5 * bench[i] + rs.normal(scale=0.1)
        
    dates = pd.date_range("2026-01-01", periods=250, freq="D")
    return pd.Series(stock, index=dates, name="stock"), pd.Series(bench, index=dates, name="bench")


@pytest.fixture
def upside_sensitive_returns():
    """Generates returns where stock is highly sensitive to benchmark rises."""
    rs = np.random.RandomState(42)
    bench = rs.normal(loc=0.0, scale=1.0, size=250)
    
    stock = np.zeros(250)
    for i in range(250):
        if bench[i] < 0:
            stock[i] = 0.5 * bench[i] + rs.normal(scale=0.1)
        else:
            stock[i] = 2.0 * bench[i] + rs.normal(scale=0.5)
        
    dates = pd.date_range("2026-01-01", periods=250, freq="D")
    return pd.Series(stock, index=dates, name="stock"), pd.Series(bench, index=dates, name="bench")


def test_quantile_beta_symmetric(symmetric_returns):
    """Verify symmetric returns result in symmetric betas around OLS beta (~1.0)."""
    stock, bench = symmetric_returns
    res = compute_quantile_beta(stock, bench)
    
    assert res["state_label"] == "symmetric_beta"
    assert abs(res["ols_beta"] - 1.0) <= 0.15
    for q in res["quantiles"]:
        assert abs(res["betas"][q] - 1.0) <= 0.25


def test_quantile_beta_downside_sensitive(downside_sensitive_returns):
    """Verify downside sensitive returns yield downside_sensitive asymmetry."""
    stock, bench = downside_sensitive_returns
    res = compute_quantile_beta(stock, bench)

    assert res["state_label"] == "downside_sensitive"
    # Beta at 5% quantile should be much higher than at 95% quantile
    assert res["betas"][0.05] > res["betas"][0.95]
    # Difference should exceed threshold (0.25)
    assert (res["betas"][0.05] - res["betas"][0.95]) > 0.25
    # A deliberately strong (2.0 vs 0.5) asymmetry: its own CIs must confirm it.
    assert res["asymmetry_significant"] is True


def test_quantile_beta_symmetric_never_flags_significance(symmetric_returns):
    """symmetric_beta carries asymmetry_significant=False by construction."""
    stock, bench = symmetric_returns
    res = compute_quantile_beta(stock, bench)
    assert res["state_label"] == "symmetric_beta"
    assert res["asymmetry_significant"] is False


def test_quantile_beta_overlapping_cis_not_significant():
    """A point-estimate asymmetry whose tail CIs overlap must NOT be called
    significant (the honesty rule the chart made visible: classification
    cannot ignore the CIs the function itself computes)."""
    # Small noisy sample: the tail betas differ by chance but their CIs are wide.
    rs = np.random.RandomState(3)
    bench = pd.Series(rs.normal(0.0, 0.01, 80))
    stock = pd.Series(1.0 * bench.values + rs.normal(0.0, 0.012, 80))
    res = compute_quantile_beta(stock, bench)

    if res["state_label"] != "symmetric_beta":
        # If noise pushed the point estimates over the threshold, the wide,
        # overlapping CIs must keep the significance flag honest.
        q_lo, q_hi = min(res["quantiles"]), max(res["quantiles"])
        cis = res["cis"]
        overlap = not (cis[q_lo][0] > cis[q_hi][1] or cis[q_hi][0] > cis[q_lo][1])
        assert overlap
        assert res["asymmetry_significant"] is False
    else:
        assert res["asymmetry_significant"] is False


def test_quantile_beta_upside_sensitive(upside_sensitive_returns):
    """Verify upside sensitive returns yield upside_sensitive asymmetry."""
    stock, bench = upside_sensitive_returns
    res = compute_quantile_beta(stock, bench)
    
    assert res["state_label"] == "upside_sensitive"
    assert res["betas"][0.05] < res["betas"][0.95]
    assert (res["betas"][0.95] - res["betas"][0.05]) > 0.25
