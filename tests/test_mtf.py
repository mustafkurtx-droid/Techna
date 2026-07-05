"""Unit and integration tests for Multiple Timeframe (MTF) weekly context module."""
from __future__ import annotations

import pandas as pd
import numpy as np

from techna.indicators.mtf import resample_to_weekly, compute_weekly_context


def test_resample_weekly_correct_values():
    """Verify daily OHLCV price resamples to weekly correctly."""
    # Create daily index from Monday 2026-06-01 to Friday 2026-06-05 (one full week)
    dates = pd.date_range(start="2026-06-01", end="2026-06-05", freq="D")
    df = pd.DataFrame({
        "Open": [10.0, 11.0, 12.0, 13.0, 14.0],
        "High": [12.0, 13.0, 14.0, 15.0, 16.0],
        "Low": [9.0, 10.0, 11.0, 12.0, 13.0],
        "Close": [11.0, 12.0, 13.0, 14.0, 15.0],
        "Volume": [100, 200, 300, 400, 500]
    }, index=dates)
    
    weekly = resample_to_weekly(df)
    assert len(weekly) == 1
    assert weekly.index[0] == pd.Timestamp("2026-06-05")  # Friday label
    assert weekly["Open"].iloc[0] == 10.0
    assert weekly["High"].iloc[0] == 16.0
    assert weekly["Low"].iloc[0] == 9.0
    assert weekly["Close"].iloc[0] == 15.0
    assert weekly["Volume"].iloc[0] == 1500


def test_partial_final_week_dropped():
    """Verify that if daily index ends on Tuesday, the last week is dropped."""
    # Monday 2026-06-01 to Tuesday 2026-06-09 (ends on Tuesday of second week)
    dates = pd.date_range(start="2026-06-01", end="2026-06-09", freq="D")
    df = pd.DataFrame({
        "Open": range(len(dates)),
        "High": range(len(dates)),
        "Low": range(len(dates)),
        "Close": range(len(dates)),
        "Volume": range(len(dates)),
    }, index=dates)
    
    weekly = resample_to_weekly(df)
    # The first week ends on Friday 2026-06-05.
    # The second week ends on Friday 2026-06-12.
    # Since last daily date (2026-06-09) is Tuesday, and 2026-06-09 < 2026-06-12 - 2 days (which is 2026-06-10),
    # the second week should be dropped.
    assert len(weekly) == 1
    assert weekly.index[-1] == pd.Timestamp("2026-06-05")


def test_partial_final_week_kept_on_wednesday():
    """Verify that if daily index ends on Wednesday, the last week is kept."""
    # Monday 2026-06-01 to Wednesday 2026-06-10 (ends on Wednesday of second week)
    dates = pd.date_range(start="2026-06-01", end="2026-06-10", freq="D")
    df = pd.DataFrame({
        "Open": range(len(dates)),
        "High": range(len(dates)),
        "Low": range(len(dates)),
        "Close": range(len(dates)),
        "Volume": range(len(dates)),
    }, index=dates)
    
    weekly = resample_to_weekly(df)
    # Wednesday 2026-06-10 is exactly Friday 2026-06-12 minus 2 days.
    # So the second week is kept.
    assert len(weekly) == 2
    assert weekly.index[-1] == pd.Timestamp("2026-06-12")


def test_alignment_state_logic():
    """Verify the alignment output logic for bullish, bearish, and mixed cases."""
    # We need a dataframe with enough history to avoid the warning (needs >= 40 weekly bars)
    # 45 weeks * 7 days = 315 daily bars
    dates = pd.date_range(start="2026-01-01", periods=320, freq="D")
    
    # Uptrend case: prices rise steadily
    df_up = pd.DataFrame({
        "Open": np.linspace(10, 100, len(dates)),
        "High": np.linspace(11, 101, len(dates)),
        "Low": np.linspace(9, 99, len(dates)),
        "Close": np.linspace(10, 100, len(dates)),
        "Volume": 100,
    }, index=dates)
    
    res_bullish = compute_weekly_context(df_up, "uptrend")
    assert res_bullish["status"] == "ok"
    assert res_bullish["weekly_trend_state"] == "uptrend"
    assert res_bullish["alignment"] == "aligned_bullish"
    
    res_mixed = compute_weekly_context(df_up, "downtrend")
    assert res_mixed["alignment"] == "mixed"

    # Downtrend case: prices fall steadily
    df_down = pd.DataFrame({
        "Open": np.linspace(100, 10, len(dates)),
        "High": np.linspace(101, 11, len(dates)),
        "Low": np.linspace(99, 9, len(dates)),
        "Close": np.linspace(100, 10, len(dates)),
        "Volume": 100,
    }, index=dates)
    
    res_bearish = compute_weekly_context(df_down, "downtrend")
    assert res_bearish["status"] == "ok"
    assert res_bearish["weekly_trend_state"] == "downtrend"
    assert res_bearish["alignment"] == "aligned_bearish"


def test_short_history_mtf_warning():
    """Verify warning fallback when weekly bars < 40."""
    dates = pd.date_range(start="2026-06-01", end="2026-06-30", freq="D")
    df = pd.DataFrame({
        "Open": range(len(dates)),
        "High": range(len(dates)),
        "Low": range(len(dates)),
        "Close": range(len(dates)),
        "Volume": range(len(dates)),
    }, index=dates)
    
    res = compute_weekly_context(df, "uptrend")
    assert res["status"] == "warning"
    assert "Insufficient history" in res["warning"]
    assert res["weekly_trend_state"] == "sideways"
    assert res["alignment"] == "mixed"
    assert np.isnan(res["weekly_rsi"])
