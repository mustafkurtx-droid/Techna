"""Offline tests for Trend indicators (validates trend.feature).

Formula References:
- SMA: Simple average over the window.
  Independent calculation: Standard Python sum/loop over list.
  Manual Anchor:
    For window 3 on golden_prices:
    Row 0: 100.00
    Row 1: 101.50
    Row 2: 102.00
    SMA[2] = (100.0 + 101.5 + 102.0) / 3 = 101.16666667
- EMA: Recursive EMA with adjust=False.
  Formula: EMA[t] = alpha * Price[t] + (1 - alpha) * EMA[t-1], where EMA[0] = Price[0].
  Independent calculation: Pure python loop with recursive formula.
  Manual Anchor:
    For span 3 on golden_prices:
    alpha = 2 / (3 + 1) = 0.5
    Row 0: 100.00 -> EMA[0] = 100.00
    Row 1: 101.50 -> EMA[1] = 0.5 * 101.50 + 0.5 * 100.00 = 100.75
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna.indicators import compute_ema, compute_sma, detect_cross, trend_state


def reference_sma(prices: list[float], window: int) -> list[float | None]:
    """Pure-Python independent implementation of SMA."""
    out: list[float | None] = []
    for i in range(len(prices)):
        if i < window - 1:
            out.append(None)
        else:
            out.append(sum(prices[i - window + 1 : i + 1]) / window)
    return out


def reference_ema(prices: list[float], span: int) -> list[float]:
    """Pure-Python independent implementation of recursive EMA (adjust=False)."""
    alpha = 2.0 / (span + 1.0)
    out: list[float] = []
    curr = prices[0]
    out.append(curr)
    for val in prices[1:]:
        curr = alpha * val + (1.0 - alpha) * curr
        out.append(curr)
    return out


def test_sma_matches_independent_computation(golden_df):
    """Scenario: SMA matches an independently computed series."""
    prices = golden_df["Close"]
    result = compute_sma(prices, window=3)
    
    # Generate golden values using independent reference implementation
    ref_vals = reference_sma(prices.tolist(), window=3)
    
    # Verify manual anchor
    assert result.iloc[2] == pytest.approx(101.166666667, rel=1e-9)
    
    # Compare entire series (skipping NaNs)
    for i in range(len(prices)):
        if ref_vals[i] is None:
            assert pd.isna(result.iloc[i])
        else:
            assert result.iloc[i] == pytest.approx(ref_vals[i], rel=1e-9)


def test_sma_warmup_rows_are_nan(golden_df):
    """Scenario: SMA warm-up rows are NaN."""
    prices = golden_df["Close"]
    result = compute_sma(prices, window=20)
    
    # The first 19 rows should be NaN
    assert result.iloc[:19].isna().all()
    # The 20th row should be a valid number
    assert not pd.isna(result.iloc[19])


def test_ema_matches_independent_recursive_computation(golden_df):
    """Scenario: EMA matches an independent recursive computation (adjust=False)."""
    prices = golden_df["Close"]
    result = compute_ema(prices, span=3)
    
    # Generate golden values using independent reference implementation
    ref_vals = reference_ema(prices.tolist(), span=3)
    
    # Verify manual anchor
    assert result.iloc[0] == pytest.approx(100.00, rel=1e-9)
    assert result.iloc[1] == pytest.approx(100.75, rel=1e-9)
    
    # Compare entire series
    for i in range(len(prices)):
        assert result.iloc[i] == pytest.approx(ref_vals[i], rel=1e-9)


def test_golden_cross_detected(golden_long_df):
    """Scenario: A golden cross is detected when the fast SMA crosses above the slow."""
    prices = golden_long_df["Close"]
    sma50 = compute_sma(prices, window=50)
    sma200 = compute_sma(prices, window=200)
    
    cross_df = detect_cross(sma50, sma200)
    
    # Verify the golden cross at index 224 (Day 225)
    # At index 223: sma50 <= sma200
    # At index 224: sma50 > sma200
    assert sma50.iloc[223] <= sma200.iloc[223]
    assert sma50.iloc[224] > sma200.iloc[224]
    
    assert cross_df["cross"].iloc[224] == "golden"
    
    # Verify that this is the only cross in the series
    crosses = cross_df[cross_df["cross"] != "none"]
    assert len(crosses) == 1
    assert crosses.index[0] == cross_df.index[224]


def test_death_cross_detected():
    """Scenario: A death cross is detected when the fast SMA crosses below the slow."""
    fast = pd.Series([10.0, 10.0, 8.0, 7.0])
    slow = pd.Series([9.0, 9.0, 9.0, 9.0])
    
    cross_df = detect_cross(fast, slow)
    
    assert cross_df["cross"].iloc[0] == "none"
    assert cross_df["cross"].iloc[1] == "none"
    assert cross_df["cross"].iloc[2] == "death"
    assert cross_df["cross"].iloc[3] == "none"


def test_no_cross_reported_during_warmup():
    """Scenario: No cross is reported during the warm-up (NaN) region."""
    # When one of the series contains NaN, no cross should be reported at that bar
    fast = pd.Series([np.nan, 10.0, np.nan])
    slow = pd.Series([9.0, 9.0, 9.0])
    
    cross_df = detect_cross(fast, slow)
    assert (cross_df["cross"] == "none").all()


def test_trend_state_reflects_alignment():
    """Scenario: trend_state reflects price/SMA alignment."""
    # 1. Uptrend: price > SMA200 and SMA50 > SMA200
    assert trend_state(120.0, 110.0, 100.0) == "uptrend"
    
    # 2. Downtrend: price < SMA200 and SMA50 < SMA200
    assert trend_state(80.0, 90.0, 100.0) == "downtrend"
    
    # 3. Sideways: mixed
    assert trend_state(105.0, 95.0, 100.0) == "sideways"  # price > SMA200, SMA50 < SMA200
    assert trend_state(95.0, 105.0, 100.0) == "sideways"  # price < SMA200, SMA50 > SMA200
    assert trend_state(np.nan, 105.0, 100.0) == "sideways"  # NaN price
