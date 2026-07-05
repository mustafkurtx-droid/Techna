"""Offline tests for Support and Resistance levels (validates levels.feature)."""
from __future__ import annotations

import pandas as pd

from techna.indicators import find_support_resistance


def test_support_and_resistance_pivots():
    """Scenario: A known local minimum/maximum is reported as support/resistance."""
    # Index 3 is a local maximum (13.0) with k=2
    # Index 8 is a local minimum (8.0) with k=2
    prices = pd.Series(
        [10.0, 11.0, 12.0, 13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0, 11.0]
    )
    
    result = find_support_resistance(prices, k=2)
    
    # Check shape
    assert list(result.columns) == ["support", "resistance"]
    assert len(result) == len(prices)
    
    # Check specific pivot points
    assert result["resistance"].iloc[3] == 13.0
    assert pd.isna(result["support"].iloc[3])
    
    assert result["support"].iloc[8] == 8.0
    assert pd.isna(result["resistance"].iloc[8])
    
    # Check that warm-up / lookahead regions are NaN
    # Since k=2, indices 0, 1 (first 2) and 10, 11 (last 2) cannot be pivots
    assert result["support"].iloc[:2].isna().all()
    assert result["resistance"].iloc[:2].isna().all()
    assert result["support"].iloc[-2:].isna().all()
    assert result["resistance"].iloc[-2:].isna().all()
    
    # Verify all other rows are NaN
    other_indices = [2, 4, 5, 6, 7, 9]
    for idx in other_indices:
        assert pd.isna(result["support"].iloc[idx])
        assert pd.isna(result["resistance"].iloc[idx])


def test_find_support_resistance_insufficient_length():
    """If the series length is less than 2k + 1, all pivots are NaN."""
    prices = pd.Series([1.0, 2.0, 3.0])
    result = find_support_resistance(prices, k=2)
    assert result["support"].isna().all()
    assert result["resistance"].isna().all()
