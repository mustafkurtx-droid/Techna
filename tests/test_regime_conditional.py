"""Offline tests for Regime-Conditional statistics (validates specs/regime_conditional.feature)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna.indicators.econometrics import (
    compute_regime_conditional_stats,
    detect_structural_breaks,
)


@pytest.fixture
def shift_series():
    """Generates a series with a volatility shift in the middle."""
    rs = np.random.RandomState(42)
    # first 150 points: low variance
    # last 150 points: high variance
    low_var = rs.normal(loc=0.0, scale=0.01, size=150)
    high_var = rs.normal(loc=0.0, scale=0.05, size=150)
    vals = np.concatenate([low_var, high_var])
    return pd.Series(vals, index=pd.date_range("2026-01-01", periods=300, freq="D"))


@pytest.fixture
def homogeneous_series():
    """Generates a homogeneous returns series with constant variance."""
    rs = np.random.RandomState(42)
    vals = rs.normal(loc=0.0, scale=0.02, size=300)
    return pd.Series(vals, index=pd.date_range("2026-01-01", periods=300, freq="D"))


def test_regime_conditional_split(shift_series):
    """Verify that a series with a break computes correct post-break statistics."""
    # Run the structural break detector
    breaks = detect_structural_breaks(shift_series, max_breaks=1)
    assert len(breaks) > 0
    
    stats = compute_regime_conditional_stats(shift_series, breaks)
    
    assert stats["is_split"] is True
    assert stats["n_full"] == 300
    assert stats["n_regime"] < 300
    assert stats["regime"]["ann_vol"] > stats["full"]["ann_vol"]
    assert stats["regime_too_short"] is False
    assert stats["regime_start"] == shift_series.index[breaks[-1]["index"]].strftime("%Y-%m-%d")


def test_regime_conditional_no_break(homogeneous_series):
    """Verify that a series with no breaks equals the full sample stats."""
    stats = compute_regime_conditional_stats(homogeneous_series, [])
    
    assert stats["is_split"] is False
    assert stats["n_full"] == 300
    assert stats["n_regime"] == 300
    assert stats["regime"]["ann_vol"] == pytest.approx(stats["full"]["ann_vol"])
    assert stats["regime"]["skew"] == pytest.approx(stats["full"]["skew"])
    assert stats["regime"]["excess_kurtosis"] == pytest.approx(stats["full"]["excess_kurtosis"])
    assert stats["regime_too_short"] is False


def test_regime_too_short_flag(homogeneous_series):
    """Verify that a break close to the end triggers the regime_too_short flag."""
    # Manually pass a break near the end (index 280 of a 300-bar series)
    mock_breaks = [{"index": 280, "date": "2026-10-08", "type": "volatility_shift"}]
    stats = compute_regime_conditional_stats(homogeneous_series, mock_breaks)
    
    assert stats["is_split"] is True
    assert stats["n_regime"] == 20
    assert stats["regime_too_short"] is True
