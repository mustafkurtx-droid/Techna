"""Offline tests for Structural Break Detection (CUSUM + binary segmentation)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna.indicators.econometrics import cusum_instability_test, detect_structural_breaks


@pytest.fixture
def vol_shift_series():
    """Generates a series with a volatility shift at index 100 with a fixed seed."""
    rs = np.random.RandomState(42)
    s1 = rs.normal(loc=0.0, scale=1.0, size=100)
    s2 = rs.normal(loc=0.0, scale=4.0, size=100)
    vals = np.concatenate([s1, s2])
    return pd.Series(vals, index=pd.date_range("2026-01-01", periods=200, freq="D"))


@pytest.fixture
def mean_shift_series():
    """Generates a series with a mean shift at index 100 with a fixed seed."""
    rs = np.random.RandomState(42)
    s1 = rs.normal(loc=0.0, scale=1.0, size=100)
    s2 = rs.normal(loc=5.0, scale=1.0, size=100)
    vals = np.concatenate([s1, s2])
    return pd.Series(vals, index=pd.date_range("2026-01-01", periods=200, freq="D"))


@pytest.fixture
def homogeneous_series():
    """Generates a homogeneous series with no breaks with a fixed seed."""
    rs = np.random.RandomState(42)
    vals = rs.normal(loc=0.0, scale=1.0, size=200)
    return pd.Series(vals, index=pd.date_range("2026-01-01", periods=200, freq="D"))


def test_structural_break_volatility_shift(vol_shift_series):
    """Verify that a volatility shift break is detected close to index 100."""
    breaks = detect_structural_breaks(vol_shift_series, min_seg=20, max_breaks=3)
    
    assert len(breaks) > 0
    # The first (most significant) break should be near index 100
    primary_break = breaks[0]
    assert abs(primary_break["index"] - 100) <= 20
    assert primary_break["type"] == "volatility_shift"


def test_structural_break_mean_shift(mean_shift_series):
    """Verify that a mean shift break is detected close to index 100."""
    breaks = detect_structural_breaks(mean_shift_series, min_seg=20, max_breaks=3)
    
    assert len(breaks) > 0
    primary_break = breaks[0]
    assert abs(primary_break["index"] - 100) <= 20
    assert primary_break["type"] == "mean_shift" or primary_break["type"] == "both"


def test_no_break_on_homogeneous_series(homogeneous_series):
    """Verify that no structural breaks are detected in a homogeneous series."""
    breaks = detect_structural_breaks(homogeneous_series, min_seg=20, max_breaks=3)
    assert len(breaks) == 0


def test_cusum_flags_instability(mean_shift_series, homogeneous_series):
    """Verify that OLS residuals CUSUM test flags structural change correctly."""
    unstable_res = cusum_instability_test(mean_shift_series)
    stable_res = cusum_instability_test(homogeneous_series)
    
    assert unstable_res["unstable"] is True
    assert stable_res["unstable"] is False
