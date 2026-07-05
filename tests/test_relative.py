"""Offline tests for Relative Strength vs Benchmark (validates relative.feature)."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.relative import align_close, rebased_performance, relative_strength, rs_state


def test_align_close():
    """Scenario: Asset and benchmark are aligned on common dates."""
    dates_a = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-04"])
    dates_b = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    
    asset = pd.Series([100.0, 101.0, 102.0], index=dates_a)
    bench = pd.Series([200.0, 201.0, 202.0], index=dates_b)
    
    aligned_a, aligned_b = align_close(asset, bench)
    
    # Common dates are 2024-01-02 and 2024-01-04
    assert len(aligned_a) == 2
    assert len(aligned_b) == 2
    assert aligned_a.index.equals(aligned_b.index)
    assert aligned_a.iloc[0] == 101.0
    assert aligned_b.iloc[0] == 200.0
    assert aligned_a.iloc[1] == 102.0
    assert aligned_b.iloc[1] == 202.0


def test_relative_strength_and_rebased():
    """Scenario: Relative strength ratio and rebased performance are calculated correctly."""
    asset = pd.Series([100.0, 110.0, 105.0])
    bench = pd.Series([200.0, 200.0, 210.0])
    
    rs = relative_strength(asset, bench)
    assert rs.iloc[0] == 0.5
    assert rs.iloc[1] == 0.55
    assert rs.iloc[2] == 0.5
    
    rebased = rebased_performance(asset)
    assert rebased.iloc[0] == pytest.approx(100.0)
    assert rebased.iloc[1] == pytest.approx(110.0)
    assert rebased.iloc[2] == pytest.approx(105.0)


def test_rs_state_logic():
    """Scenario: rs_state reflects whether the asset is out/under-performing."""
    # Outperforming: RS > RS_MA and RS is increasing
    rs_out = pd.Series([0.5, 0.52])
    ma_out = pd.Series([0.5, 0.51])
    assert rs_state(rs_out, ma_out) == "outperforming"
    
    # Underperforming: RS < RS_MA and RS is decreasing
    rs_under = pd.Series([0.5, 0.48])
    ma_under = pd.Series([0.5, 0.49])
    assert rs_state(rs_under, ma_under) == "underperforming"
    
    # Neutral: RS > RS_MA but decreasing
    rs_neutral1 = pd.Series([0.55, 0.53])
    ma_neutral1 = pd.Series([0.5, 0.51])
    assert rs_state(rs_neutral1, ma_neutral1) == "neutral"
    
    # Neutral: RS < RS_MA but increasing
    rs_neutral2 = pd.Series([0.45, 0.47])
    ma_neutral2 = pd.Series([0.5, 0.49])
    assert rs_state(rs_neutral2, ma_neutral2) == "neutral"
