"""Offline tests for Momentum indicators (validates momentum.feature).

Formula References:
- RSI: Wilder smoothing (alpha = 1/period).
  First value is SMA of first 'period' changes.
  Subsequent values are recursively smoothed.
  Manual Anchor (period 3):
    Prices: [100.0, 101.5, 102.0, 101.0, 103.5]
    Changes: [1.5, 0.5, -1.0, 2.5]
    Gains: [1.5, 0.5, 0.0, 2.5]
    Losses: [0.0, 0.0, 1.0, 0.0]
    At index 3:
      avg_gain = (1.5 + 0.5 + 0.0) / 3 = 0.66666667
      avg_loss = (0.0 + 0.0 + 1.0) / 3 = 0.33333333
      RS = 2.0 -> RSI = 100 - (100 / (1 + 2)) = 66.66666667
    At index 4:
      avg_gain = (0.66666667 * 2 + 2.5) / 3 = 1.27777778
      avg_loss = (0.33333333 * 2 + 0.0) / 3 = 0.22222222
      RS = 5.75 -> RSI = 100 - (100 / (1 + 5.75)) = 85.18518519
"""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators import compute_macd, compute_rsi, macd_state, rsi_state


def reference_rsi(prices: list[float], period: int = 14) -> list[float | None]:
    """Pure-Python independent implementation of Wilder RSI."""
    if len(prices) <= period:
        return [None] * len(prices)
        
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [c if c > 0 else 0.0 for c in changes]
    losses = [-c if c < 0 else 0.0 for c in changes]
    
    out: list[float | None] = [None] * len(prices)
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        out[period] = 100.0 if avg_gain > 0 else 50.0
    else:
        out[period] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
        
    for i in range(period + 1, len(prices)):
        g = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        
        if avg_loss == 0:
            out[i] = 100.0 if avg_gain > 0 else 50.0
        else:
            out[i] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
            
    return out


def reference_ema_list(prices: list[float], span: int) -> list[float]:
    """Pure-Python recursive EMA (adjust=False)."""
    alpha = 2.0 / (span + 1.0)
    out: list[float] = []
    curr = prices[0]
    out.append(curr)
    for val in prices[1:]:
        curr = alpha * val + (1.0 - alpha) * curr
        out.append(curr)
    return out


def test_rsi_matches_independent_wilder_smoothing(golden_df):
    """Scenario: RSI matches an independent Wilder-smoothing computation."""
    prices = golden_df["Close"]
    result = compute_rsi(prices, period=14)
    ref_vals = reference_rsi(prices.tolist(), period=14)
    
    # Check that warm-up is NaN
    assert result.iloc[:14].isna().all()
    
    # Check that rest matches
    for i in range(14, len(prices)):
        assert result.iloc[i] == pytest.approx(ref_vals[i], rel=1e-9)


def test_rsi_manual_anchor():
    """Verify RSI calculation against manual anchor values."""
    prices = pd.Series([100.0, 101.5, 102.0, 101.0, 103.5])
    result = compute_rsi(prices, period=3)
    
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert pd.isna(result.iloc[2])
    assert result.iloc[3] == pytest.approx(66.66666667, rel=1e-9)
    assert result.iloc[4] == pytest.approx(85.18518519, rel=1e-9)


def test_rsi_bounds(golden_df):
    """Scenario: RSI stays within the closed interval 0..100."""
    prices = golden_df["Close"]
    result = compute_rsi(prices, period=14)
    valid_rsi = result.dropna()
    assert (valid_rsi >= 0.0).all()
    assert (valid_rsi <= 100.0).all()


def test_rsi_warmup_nan(golden_df):
    """Scenario: RSI is NaN during the warm-up period."""
    prices = golden_df["Close"]
    result = compute_rsi(prices, period=14)
    assert result.iloc[:13].isna().all()
    assert not pd.isna(result.iloc[14])


def test_macd_math_matches_independent_calculation(golden_df):
    """Scenario: MACD line, signal and histogram match independent EMA math."""
    prices = golden_df["Close"]
    macd_df = compute_macd(prices, fast=12, slow=26, signal=9)
    
    # Generate reference values
    price_list = prices.tolist()
    ref_fast = reference_ema_list(price_list, 12)
    ref_slow = reference_ema_list(price_list, 26)
    ref_macd = [f - s for f, s in zip(ref_fast, ref_slow)]
    ref_signal = reference_ema_list(ref_macd, 9)
    ref_hist = [m - s for m, s in zip(ref_macd, ref_signal)]
    
    for i in range(len(prices)):
        assert macd_df["macd"].iloc[i] == pytest.approx(ref_macd[i], rel=1e-9)
        assert macd_df["signal"].iloc[i] == pytest.approx(ref_signal[i], rel=1e-9)
        assert macd_df["hist"].iloc[i] == pytest.approx(ref_hist[i], rel=1e-9)


def test_rsi_state_mapping():
    """Scenario: rsi_state maps thresholds to overbought/oversold/neutral."""
    assert rsi_state(75.0) == "overbought"
    assert rsi_state(70.0) == "overbought"
    assert rsi_state(30.0) == "oversold"
    assert rsi_state(25.0) == "oversold"
    assert rsi_state(50.0) == "neutral"
    assert rsi_state(float("nan")) == "neutral"


def test_macd_state_mapping():
    """Scenario: macd_state maps values to bullish/bearish."""
    # Bullish when hist > 0
    assert macd_state(0.5) == "bullish"
    # Bearish when hist <= 0
    assert macd_state(-0.2) == "bearish"
    assert macd_state(0.0) == "bearish"
    assert macd_state(float("nan")) == "bearish"
