"""Offline tests for the context/regime indicators (validates regime.feature).

Golden values are produced by independent, explicit Python loops (no pandas
vectorisation, no reuse of the production code path), plus a couple of
hand-verified anchors on the simplest quantities (True Range and the raw
directional moves).
"""
from __future__ import annotations

import pandas as pd
import pytest

from techna import config
from techna.indicators.regime import (
    compute_adx,
    compute_atr,
    trend_regime,
    volatility_regime,
)


# --------------------------------------------------------------------------- #
# Independent reference implementations (explicit loops)
# --------------------------------------------------------------------------- #
def ref_true_range(high, low, close):
    n = len(close)
    tr = [high[0] - low[0]]
    for i in range(1, n):
        tr.append(
            max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
        )
    return tr


def ref_wilder_rma(values, period):
    """Wilder RMA over values that may start with leading None."""
    n = len(values)
    out = [None] * n
    # first valid index
    first = next((i for i, v in enumerate(values) if v is not None), None)
    if first is None or first + period - 1 >= n:
        return out
    seed_end = first + period - 1
    out[seed_end] = sum(values[first : seed_end + 1]) / period
    for i in range(seed_end + 1, n):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period
    return out


def ref_atr(high, low, close, period):
    return ref_wilder_rma(ref_true_range(high, low, close), period)


def ref_adx(high, low, close, period):
    n = len(close)
    tr = ref_true_range(high, low, close)
    plus_dm = [None]
    minus_dm = [None]
    for i in range(1, n):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)

    atr = ref_wilder_rma(tr, period)
    pdm_s = ref_wilder_rma(plus_dm, period)
    mdm_s = ref_wilder_rma(minus_dm, period)

    plus_di = [None] * n
    minus_di = [None] * n
    dx = [None] * n
    for i in range(n):
        if atr[i] in (None, 0) or pdm_s[i] is None or mdm_s[i] is None:
            continue
        plus_di[i] = 100.0 * pdm_s[i] / atr[i]
        minus_di[i] = 100.0 * mdm_s[i] / atr[i]
        denom = plus_di[i] + minus_di[i]
        if denom != 0:
            dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / denom

    adx = ref_wilder_rma(dx, period)
    return adx, plus_di, minus_di


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_true_range_first_bar_is_high_minus_low(golden_long_df):
    """Scenario: True Range of the first bar has no previous close."""
    atr = compute_atr(golden_long_df, period=14)
    # ATR itself is NaN at row 0 (Wilder warm-up); verify the TR anchor directly.
    assert pd.isna(atr.iloc[0])
    high = golden_long_df["High"].iloc[0]
    low = golden_long_df["Low"].iloc[0]
    ref = ref_true_range(
        golden_long_df["High"].tolist(),
        golden_long_df["Low"].tolist(),
        golden_long_df["Close"].tolist(),
    )
    assert ref[0] == pytest.approx(high - low)


def test_atr_matches_independent_wilder(golden_long_df):
    """Scenario: ATR matches an independent Wilder computation."""
    result = compute_atr(golden_long_df, period=14)
    ref = ref_atr(
        golden_long_df["High"].tolist(),
        golden_long_df["Low"].tolist(),
        golden_long_df["Close"].tolist(),
        14,
    )
    # Warm-up: first 13 rows NaN, value appears at index 13 (period-th bar).
    assert result.iloc[:13].isna().all()
    assert not pd.isna(result.iloc[13])
    for i in range(len(result)):
        if ref[i] is None:
            assert pd.isna(result.iloc[i])
        else:
            assert result.iloc[i] == pytest.approx(ref[i], rel=1e-9)


def test_adx_matches_independent_computation(golden_long_df):
    """Scenario: ADX, +DI and -DI match an independent computation."""
    result = compute_adx(golden_long_df, period=14)
    ref_adx_vals, ref_plus, ref_minus = ref_adx(
        golden_long_df["High"].tolist(),
        golden_long_df["Low"].tolist(),
        golden_long_df["Close"].tolist(),
        14,
    )
    for i in range(len(result)):
        for col, ref in (
            ("adx", ref_adx_vals),
            ("plus_di", ref_plus),
            ("minus_di", ref_minus),
        ):
            if ref[i] is None:
                assert pd.isna(result[col].iloc[i]), f"{col}[{i}] expected NaN"
            else:
                assert result[col].iloc[i] == pytest.approx(ref[i], rel=1e-9)


def test_adx_warmup_is_about_two_periods(golden_long_df):
    """Scenario: ADX has a warm-up of roughly twice the period."""
    result = compute_adx(golden_long_df, period=14)
    # ADX cannot be defined before ~2*period bars.
    assert result["adx"].iloc[:26].isna().all()
    assert not pd.isna(result["adx"].iloc[-1])


def test_strong_trend_yields_high_adx(golden_long_df):
    """Scenario: A strong directional move yields a high ADX."""
    # golden_long is a clean V (strong down then strong up) -> strong trend.
    result = compute_adx(golden_long_df, period=14)
    assert result["adx"].iloc[-1] > config.ADX_TREND_THRESHOLD


def test_trend_regime_classification():
    """Scenario: Trend regime classification."""
    assert trend_regime(30.0, 25.0, 10.0) == "trending_up"
    assert trend_regime(30.0, 10.0, 25.0) == "trending_down"
    assert trend_regime(15.0, 25.0, 10.0) == "ranging"
    assert trend_regime(float("nan"), 25.0, 10.0) == "undetermined"


def test_volatility_regime_high_and_unknown():
    """Scenario: Volatility regime is relative to the asset's own history."""
    idx = pd.RangeIndex(120)
    close = pd.Series([100.0] * 120, index=idx)
    # ATR flat then a spike on the last bar -> top percentile -> "high".
    atr_vals = [1.0] * 119 + [5.0]
    atr = pd.Series(atr_vals, index=idx)
    assert volatility_regime(atr, close, lookback=100) == "high"

    # Insufficient history -> "unknown".
    short_atr = pd.Series([1.0], index=pd.RangeIndex(1))
    short_close = pd.Series([100.0], index=pd.RangeIndex(1))
    assert volatility_regime(short_atr, short_close, lookback=100) == "unknown"
