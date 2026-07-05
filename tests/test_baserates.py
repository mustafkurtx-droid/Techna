"""Offline tests for Empirical Base Rates (validates baserates.feature)."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.baserates import baseline_stats, conditional_stats, forward_return


def test_forward_return():
    """Scenario: Forward returns shift price by the horizon and tail is NaN."""
    close = pd.Series([100.0, 102.0, 105.0, 103.0, 106.0])
    
    # Horizon = 2
    # Returns at index t = close[t + 2] / close[t] - 1
    # index 0: close[2] / close[0] - 1 = 105 / 100 - 1 = 0.05
    # index 1: close[3] / close[1] - 1 = 103 / 102 - 1 = 103/102 - 1 = 0.00980392
    # index 2: close[4] / close[2] - 1 = 106 / 105 - 1 = 106/105 - 1 = 0.0095238
    # index 3: NaN
    # index 4: NaN
    
    fwd = forward_return(close, horizon=2)
    
    assert len(fwd) == 5
    assert fwd.iloc[0] == pytest.approx(0.05)
    assert fwd.iloc[1] == pytest.approx(103.0 / 102.0 - 1.0)
    assert fwd.iloc[2] == pytest.approx(106.0 / 105.0 - 1.0)
    assert pd.isna(fwd.iloc[3])
    assert pd.isna(fwd.iloc[4])


def test_conditional_stats():
    """Scenario: Conditional stats summarise only the bars where the condition holds."""
    # Let's define a forward return series and a condition series
    fwd = pd.Series([0.05, -0.02, 0.03, 0.01, -0.04, 0.08])
    condition = pd.Series([True, False, True, True, False, True])
    
    # Matches:
    # index 0: 0.05 (positive)
    # index 2: 0.03 (positive)
    # index 3: 0.01 (positive)
    # index 5: 0.08 (positive)
    # Selected: [0.05, 0.03, 0.01, 0.08]
    # n = 4
    # mean = (0.05 + 0.03 + 0.01 + 0.08) / 4 = 0.17 / 4 = 0.0425
    # sorted: [0.01, 0.03, 0.05, 0.08]
    # median = (0.03 + 0.05) / 2 = 0.04
    # win_rate = 4 / 4 = 1.0
    
    stats = conditional_stats(condition, fwd, min_sample=3)
    
    assert stats["n"] == 4
    assert stats["mean"] == pytest.approx(0.0425)
    assert stats["median"] == pytest.approx(0.04)
    assert stats["win_rate"] == 1.0
    assert stats["reliable"] is True
    
    # Check min_sample failure
    stats_unreliable = conditional_stats(condition, fwd, min_sample=5)
    assert stats_unreliable["reliable"] is False


def test_baseline_stats():
    """Scenario: Baseline stats use all bars."""
    fwd = pd.Series([0.05, -0.02, 0.03, 0.01, -0.04, 0.08, float("nan")])
    
    # Selected all non-nan: [0.05, -0.02, 0.03, 0.01, -0.04, 0.08]
    # n = 6
    # mean = (0.05 - 0.02 + 0.03 + 0.01 - 0.04 + 0.08) / 6 = 0.11 / 6 = 0.0183333
    # positive: 0.05, 0.03, 0.01, 0.08 (4 positive returns)
    # win_rate = 4 / 6 = 0.6666666
    
    stats = baseline_stats(fwd)
    
    assert stats["n"] == 6
    assert stats["mean"] == pytest.approx(0.11 / 6.0)
    assert stats["win_rate"] == pytest.approx(4.0 / 6.0)
