"""Offline tests for drawdown series and episodes indicator (validates risk_drawdown.feature)."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.risk_context import compute_drawdown_series, find_drawdown_episodes


def test_drawdown_series_accuracy():
    """Scenario: Verify drawdown series matches running max."""
    close = pd.Series([100.0, 80.0, 110.0, 99.0])
    # expected max: [100.0, 100.0, 110.0, 110.0]
    # expected dd:  [0.0, -0.20, 0.0, -0.10]
    df_dd = compute_drawdown_series(close)
    
    assert list(df_dd["running_max"]) == [100.0, 100.0, 110.0, 110.0]
    assert list(df_dd["drawdown"]) == pytest.approx([0.0, -0.20, 0.0, -0.10])


def test_drawdown_episode_detection():
    """Scenario: Detect multiple drawdown episodes, peak, trough, and recovery dates."""
    dates = pd.date_range("2024-01-01", periods=6)
    close = pd.Series([100.0, 80.0, 100.0, 120.0, 90.0, 120.0], index=dates)
    # Price path:
    # 0: 100 (peak)
    # 1: 80 (trough, -20%)
    # 2: 100 (recovery)
    # 3: 120 (new peak)
    # 4: 90 (trough, -25%)
    # 5: 120 (recovery)
    
    episodes = find_drawdown_episodes(close, top_n=3)
    
    # We should have 2 episodes, sorted by trough severity (most negative first)
    assert len(episodes) == 2
    
    # Severe episode first: peak 120 (index 3), trough 90 (index 4), recovery 120 (index 5)
    assert episodes[0]["trough_pct"] == pytest.approx(-0.25)
    assert episodes[0]["peak_date"] == dates[3].strftime("%Y-%m-%d")
    assert episodes[0]["trough_date"] == dates[4].strftime("%Y-%m-%d")
    assert episodes[0]["recovery_date"] == dates[5].strftime("%Y-%m-%d")
    assert episodes[0]["days_to_recover"] == 1
    
    # Second episode: peak 100 (index 0), trough 80 (index 1), recovery 100 (index 2)
    assert episodes[1]["trough_pct"] == pytest.approx(-0.20)
    assert episodes[1]["peak_date"] == dates[0].strftime("%Y-%m-%d")
    assert episodes[1]["trough_date"] == dates[1].strftime("%Y-%m-%d")
    assert episodes[1]["recovery_date"] == dates[2].strftime("%Y-%m-%d")
    assert episodes[1]["days_to_recover"] == 1
