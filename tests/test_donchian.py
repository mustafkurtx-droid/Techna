"""Unit tests for the Donchian Channels indicator and daily breakout events."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.donchian import compute_donchian
from techna.indicators.events import compute_events


def test_donchian_channels_calculation():
    """Verify Donchian upper/lower bands and position percentages are accurate."""
    dates = pd.date_range("2026-01-01", periods=60)
    
    # Generate linear price: High goes from 10 to 69, Low goes from 0 to 59, Close is 5 + index
    high = [10.0 + i for i in range(60)]
    low = [0.0 + i for i in range(60)]
    close = [5.0 + i for i in range(60)]
    
    df = pd.DataFrame({
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": [1000] * 60,
    }, index=dates)
    
    res = compute_donchian(df, fast=20, slow=55)

    # Channels EXCLUDE the current bar (shift(1)) -- the band at index 59 is
    # the extreme of the PRIOR 20 bars (indices 39..58), never today's.
    # upper_20 = max(High[39:59]) = 10 + 58 = 68.0
    # lower_20 = min(Low[39:59])  =  0 + 39 = 39.0
    # Close is 5 + 59 = 64.0.
    # pos_pct_20 = 100 * (64.0 - 39.0) / (68.0 - 39.0) = 100 * 25.0 / 29.0 = 86.2069%
    assert res["upper_20"].iloc[-1] == 68.0
    assert res["lower_20"].iloc[-1] == 39.0
    assert res["pos_pct_20"].iloc[-1] == pytest.approx(86.2069, rel=1e-3)

    # For slow=55: at index 59, upper_55 = max(High[4:59]) = 10 + 58 = 68.0
    # lower_55 = min(Low[4:59]) = 0 + 4 = 4.0
    # Close is 64.0.
    # pos_pct_55 = 100 * (64.0 - 4.0) / (68.0 - 4.0) = 100 * 60.0 / 64.0 = 93.75%
    assert res["upper_55"].iloc[-1] == 68.0
    assert res["lower_55"].iloc[-1] == 4.0
    assert res["pos_pct_55"].iloc[-1] == pytest.approx(93.75, rel=1e-3)


def test_donchian_no_lookahead_today_cannot_lift_its_own_band():
    """FROZEN spec rule: today's new high must NOT raise today's band.

    If the current bar were included in the rolling window, High > upper
    would be impossible by construction and breakouts could never fire.
    """
    dates = pd.date_range("2026-01-01", periods=30)
    high = [10.0] * 29 + [50.0]   # today spikes to a fresh extreme
    low = [5.0] * 30
    close = [8.0] * 29 + [45.0]

    df = pd.DataFrame({
        "High": high, "Low": low, "Close": close, "Volume": [1000] * 30,
    }, index=dates)

    res = compute_donchian(df, fast=20, slow=25)

    # Today's band reflects only PRIOR bars: still 10.0, not 50.0.
    assert res["upper_20"].iloc[-1] == 10.0
    # Therefore today's high (50) exceeds the band -> a detectable breakout.
    assert df["High"].iloc[-1] > res["upper_20"].iloc[-1]
    # Warm-up: with shift(1), the first valid band value is at index `fast`,
    # one bar later than an unshifted rolling window would give.
    assert res["upper_20"].iloc[:20].isna().all()
    assert not pd.isna(res["upper_20"].iloc[20])


def test_donchian_breakout_events():
    """Verify donchian_breakout triggers bullish/bearish breakouts correctly."""
    dates = pd.date_range("2026-01-01", periods=5)
    
    # 1. Bullish breakout: Close exceeds previous upper band
    df_d1 = pd.DataFrame({
        "upper_20": [100.0] * 5,
        "lower_20": [90.0] * 5,
        "upper_55": [105.0] * 5,
        "lower_55": [85.0] * 5,
    }, index=dates)
    
    context1 = {
        "donchian": {
            "status": "ok",
            "_df": df_d1,
            "_close_series": pd.Series([95.0, 95.0, 95.0, 95.0, 102.0], index=dates), # Breakout 20-day, but not 55-day
        }
    }
    ev1 = compute_events(context1)
    assert len(ev1) == 1
    assert ev1[0]["type"] == "donchian_breakout"
    assert ev1[0]["direction"] == "bullish"
    assert "Upper 20-day band" in ev1[0]["detail"]
    
    # 2. Bearish breakout: Close drops below previous lower band
    context2 = {
        "donchian": {
            "status": "ok",
            "_df": df_d1,
            "_close_series": pd.Series([95.0, 95.0, 95.0, 95.0, 82.0], index=dates), # Breakout both 20-day and 55-day lower
        }
    }
    ev2 = compute_events(context2)
    # Triggers for both 20-day and 55-day channels
    assert len(ev2) == 2
    types = [ev["type"] for ev in ev2]
    assert all(t == "donchian_breakout" for t in types)
    directions = [ev["direction"] for ev in ev2]
    assert all(d == "bearish" for d in directions)
