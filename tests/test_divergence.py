"""Offline tests for price/oscillator divergence (validates divergence.feature)."""
from __future__ import annotations

import pandas as pd

from techna.indicators.divergence import detect_divergence, find_swings


def test_swings_not_confirmed_near_edges():
    """Scenario: Swing points near the edges are not confirmed."""
    # Strictly increasing then decreasing: a single peak in the middle.
    prices = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 4.0, 3.0, 2.0, 1.0])
    highs, lows = find_swings(prices, k=2)
    # The peak at index 4 should be a confirmed swing high.
    assert (4, 5.0) in highs
    # No swing within k=2 of either end.
    for pos, _ in highs + lows:
        assert 2 <= pos <= len(prices) - 1 - 2


def test_bearish_divergence_detected():
    """Scenario: Bearish divergence (price higher high, oscillator lower high)."""
    # Two price peaks: second higher than first.
    price = pd.Series(
        [10, 12, 10, 8, 10, 13, 10, 8, 6, 4]  # peaks at idx 1 (12) and 5 (13)
    ).astype(float)
    # Oscillator peaks at the same positions: second LOWER than first.
    osc = pd.Series(
        [50, 80, 50, 40, 50, 70, 50, 40, 30, 20]  # 80 then 70 -> lower high
    ).astype(float)

    result = detect_divergence(price, osc, k=1, lookback=60)
    assert result["bearish"] is True
    assert result["bullish"] is False
    assert "bearish" in (result["detail"] or "")


def test_bullish_divergence_detected():
    """Scenario: Bullish divergence (price lower low, oscillator higher low)."""
    # Two price troughs: second lower than first.
    price = pd.Series(
        [10, 8, 10, 12, 10, 7, 10, 12, 14, 16]  # troughs at idx 1 (8) and 5 (7)
    ).astype(float)
    # Oscillator troughs at the same positions: second HIGHER than first.
    osc = pd.Series(
        [50, 20, 50, 60, 50, 30, 50, 60, 70, 80]  # 20 then 30 -> higher low
    ).astype(float)

    result = detect_divergence(price, osc, k=1, lookback=60)
    assert result["bullish"] is True
    assert result["bearish"] is False


def test_no_divergence_when_in_agreement():
    """Scenario: No divergence when price and oscillator agree."""
    # Price higher high AND oscillator higher high -> no bearish divergence.
    price = pd.Series([10, 12, 10, 8, 10, 14, 10, 8, 6, 4]).astype(float)
    osc = pd.Series([50, 70, 50, 40, 50, 85, 50, 40, 30, 20]).astype(float)

    result = detect_divergence(price, osc, k=1, lookback=60)
    assert result["bearish"] is False
    assert result["bullish"] is False
