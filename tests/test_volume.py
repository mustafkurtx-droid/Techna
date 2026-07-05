"""Offline tests for Volume Analysis (validates volume.feature)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna.indicators.volume import (
    compute_obv,
    detect_obv_divergence,
    compute_vwap,
    vwap_state,
)


def test_obv_calculation_accuracy():
    """Scenario: OBV adds volume on up days, subtracts on down days, holds when unchanged.
    
    Independent Golden Values Calculation:
    Prices:  [10.0, 11.0, 10.5, 10.5, 12.0]
    Volumes: [1000, 2000, 1500, 1800, 2500]
    Expected OBV:
    Day 0: 0.0 (Starting convention)
    Day 1: Close 11.0 > 10.0 => 0.0 + 2000 = 2000.0
    Day 2: Close 10.5 < 11.0 => 2000.0 - 1500 = 500.0
    Day 3: Close 10.5 == 10.5 => 500.0 (unchanged)
    Day 4: Close 12.0 > 10.5 => 500.0 + 2500 = 3000.0
    """
    close = pd.Series([10.0, 11.0, 10.5, 10.5, 12.0])
    volume = pd.Series([1000, 2000, 1500, 1800, 2500])
    
    obv = compute_obv(close, volume)
    
    assert obv.iloc[0] == 0.0
    assert obv.iloc[1] == 2000.0
    assert obv.iloc[2] == 500.0
    assert obv.iloc[3] == 500.0
    assert obv.iloc[4] == 3000.0
    
    # Input mismatch error check
    with pytest.raises(ValueError):
        compute_obv(close, volume.iloc[:-1])


def test_obv_divergence_detection():
    """Scenario: OBV divergence flags bullish when price falls but OBV rises; bearish when price rises but OBV falls.
    
    Verification method:
    Closed-form slope: slope = cov(x, y) / var(x)
    """
    # 1. Bullish Divergence (Price falling, OBV rising)
    # Price:  [10, 9, 8, 7] -> clearly falling (negative slope)
    # OBV:    [100, 110, 120, 130] -> clearly rising (positive slope)
    close_bull = pd.Series([10.0, 9.0, 8.0, 7.0])
    obv_bull = pd.Series([100.0, 110.0, 120.0, 130.0])
    
    div_bull = detect_obv_divergence(close_bull, obv_bull, lookback=4)
    assert div_bull["state"] == "bullish_divergence"
    assert div_bull["price_slope"] < 0
    assert div_bull["obv_slope"] > 0
    
    # 2. Bearish Divergence (Price rising, OBV falling)
    # Price:  [10, 11, 12, 13] -> rising
    # OBV:    [100, 90, 80, 70] -> falling
    close_bear = pd.Series([10.0, 11.0, 12.0, 13.0])
    obv_bear = pd.Series([100.0, 90.0, 80.0, 70.0])
    
    div_bear = detect_obv_divergence(close_bear, obv_bear, lookback=4)
    assert div_bear["state"] == "bearish_divergence"
    assert div_bear["price_slope"] > 0
    assert div_bear["obv_slope"] < 0
    
    # 3. Confirming (Both rising)
    close_conf = pd.Series([10.0, 11.0, 12.0, 13.0])
    obv_conf = pd.Series([100.0, 110.0, 120.0, 130.0])
    div_conf = detect_obv_divergence(close_conf, obv_conf, lookback=4)
    assert div_conf["state"] == "confirming"
    
    # 4. Neutral (Flat slopes)
    close_neut = pd.Series([10.0, 10.0, 10.0, 10.0])
    obv_neut = pd.Series([100.0, 100.0, 100.0, 100.0])
    div_neut = detect_obv_divergence(close_neut, obv_neut, lookback=4)
    assert div_neut["state"] == "neutral"


def test_vwap_calculation_accuracy(golden_df):
    """Scenario: Full and rolling VWAP calculation checks.
    
    Verification method:
    Calculates TP = (H+L+C)/3 and cumulative sum of TP*Vol divided by cumulative sum of Vol.
    """
    df = golden_df.copy()
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    volume = df["Volume"]
    
    # 1. Full VWAP (Anchored)
    vwap_full = compute_vwap(high, low, close, volume, period=None)

    # Independent hand-computed anchors, derived from the canonical weighted-average
    # definition using the actual fixture rows (NOT the production cumsum path).
    # Row 0: TP = (100.5 + 99.5 + 100.0)/3 = 100.0 ; VWAP[0] = TP[0] = 100.0
    assert vwap_full.iloc[0] == pytest.approx(100.0)
    # Row 1: TP = (102.0 + 99.5 + 101.5)/3 = 101.0
    #   VWAP[1] = (100.0*1_000_000 + 101.0*1_001_000) / (1_000_000 + 1_001_000)
    expected_vwap_1 = (100.0 * 1_000_000 + 101.0 * 1_001_000) / (1_000_000 + 1_001_000)
    assert vwap_full.iloc[1] == pytest.approx(expected_vwap_1)

    # Whole-series cross-check against the cumulative definition.
    tp = (high + low + close) / 3.0
    expected_full = (tp * volume).cumsum() / volume.cumsum()
    pd.testing.assert_series_equal(vwap_full, expected_full.rename("VWAP"))
    
    # 2. Rolling VWAP
    N = 20
    vwap_roll = compute_vwap(high, low, close, volume, period=N)
    
    # First N-1 should be NaN
    assert vwap_roll.iloc[:N-1].isna().all()
    
    # Row N reference calculation
    expected_n = (tp.iloc[:N] * volume.iloc[:N]).sum() / volume.iloc[:N].sum()
    assert vwap_roll.iloc[N-1] == pytest.approx(expected_n)


def test_price_vs_vwap_state():
    """Scenario: Price-vs-VWAP above/below state and distance calculation."""
    close = pd.Series([100.0, 105.0])
    vwap = pd.Series([98.0, 100.0])
    
    # Last close (105) vs last vwap (100)
    # Expected state: above_vwap, distance: 5.0%
    state_above = vwap_state(close, vwap)
    assert state_above["state"] == "above_vwap"
    assert state_above["distance_pct"] == pytest.approx(5.0)
    
    # Case: below_vwap
    close_below = pd.Series([100.0, 95.0])
    state_below = vwap_state(close_below, vwap)
    assert state_below["state"] == "below_vwap"
    assert state_below["distance_pct"] == pytest.approx(-5.0)
    
    # Case: inf close
    state_inf_close = vwap_state(pd.Series([100.0, float("inf")]), vwap)
    assert state_inf_close["state"] == "unknown"
    assert np.isnan(state_inf_close["distance_pct"])
    
    # Case: inf vwap
    state_inf_vwap = vwap_state(close, pd.Series([98.0, float("inf")]))
    assert state_inf_vwap["state"] == "unknown"
    assert np.isnan(state_inf_vwap["distance_pct"])
