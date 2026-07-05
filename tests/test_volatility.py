"""Offline tests for Bollinger Bands volatility indicator (validates volatility.feature).

Formula References:
- Mid: SMA20
- Standard Deviation: population standard deviation (ddof=0)
- Upper: Mid + 2 * std
- Lower: Mid - 2 * std
- pct_b: (Price - Lower) / (Upper - Lower)
- bandwidth: (Upper - Lower) / Mid
"""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators import bollinger_state, compute_bollinger


def reference_bollinger(
    prices: list[float],
    window: int = 20,
    num_std: float = 2.0,
) -> list[dict]:
    """Pure-Python independent implementation of Bollinger Bands (ddof=0)."""
    out: list[dict] = []
    for i in range(len(prices)):
        if i < window - 1:
            out.append(
                {
                    "mid": None,
                    "upper": None,
                    "lower": None,
                    "pct_b": None,
                    "bandwidth": None,
                }
            )
        else:
            sub = prices[i - window + 1 : i + 1]
            mid = sum(sub) / window
            # Population variance (ddof=0)
            variance = sum((x - mid) ** 2 for x in sub) / window
            std = variance ** 0.5
            upper = mid + num_std * std
            lower = mid - num_std * std
            diff = upper - lower
            p = prices[i]
            pct_b = (p - lower) / diff if diff != 0 else 0.5
            bandwidth = diff / mid if mid != 0 else 0.0
            out.append(
                {
                    "mid": mid,
                    "upper": upper,
                    "lower": lower,
                    "pct_b": pct_b,
                    "bandwidth": bandwidth,
                }
            )
    return out


def test_bollinger_matches_independent_computation(golden_df):
    """Scenario: Bands match an independent rolling mean/std (ddof=0) computation."""
    prices = golden_df["Close"]
    result = compute_bollinger(prices, window=20, num_std=2.0)
    ref_vals = reference_bollinger(prices.tolist(), window=20, num_std=2.0)
    
    # Check that warm-up is NaN
    assert result.iloc[:19].isna().any(axis=1).all()
    
    # Check that the rest matches the independent reference
    for i in range(19, len(prices)):
        assert result["mid"].iloc[i] == pytest.approx(ref_vals[i]["mid"], rel=1e-9)
        assert result["upper"].iloc[i] == pytest.approx(ref_vals[i]["upper"], rel=1e-9)
        assert result["lower"].iloc[i] == pytest.approx(ref_vals[i]["lower"], rel=1e-9)
        assert result["pct_b"].iloc[i] == pytest.approx(ref_vals[i]["pct_b"], rel=1e-9)
        assert result["bandwidth"].iloc[i] == pytest.approx(ref_vals[i]["bandwidth"], rel=1e-9)


def test_bollinger_band_ordering_invariant(golden_df):
    """Scenario: Band ordering invariant holds: upper >= mid >= lower everywhere non-NaN."""
    prices = golden_df["Close"]
    result = compute_bollinger(prices, window=20)
    valid_bands = result.dropna()
    
    assert (valid_bands["upper"] >= valid_bands["mid"]).all()
    assert (valid_bands["mid"] >= valid_bands["lower"]).all()


def test_bollinger_warmup_nan(golden_df):
    """Scenario: Bands are NaN during the warm-up period."""
    prices = golden_df["Close"]
    result = compute_bollinger(prices, window=20)
    
    assert result.iloc[:19]["mid"].isna().all()
    assert result.iloc[:19]["upper"].isna().all()
    assert result.iloc[:19]["lower"].isna().all()
    assert not pd.isna(result.iloc[19]["mid"])


def test_bollinger_state_mapping():
    """Verify that bollinger_state properly maps prices to band levels."""
    assert bollinger_state(120.0, 110.0, 100.0, 90.0) == "above_upper"
    assert bollinger_state(85.0, 110.0, 100.0, 90.0) == "below_lower"
    assert bollinger_state(100.0, 110.0, 100.0, 90.0) == "within_bands"
    assert bollinger_state(float("nan"), 110.0, 100.0, 90.0) == "within_bands"
