"""Unit and integration tests for the event detection engine (events module)."""
from __future__ import annotations

import pandas as pd

from techna.indicators.events import compute_events


def test_no_events_detected():
    """Verify that an empty/stable series returns no events and correct finding."""
    dates = pd.date_range("2026-01-01", periods=10)
    df = pd.DataFrame({
        "Open": [100.0] * 10,
        "High": [100.0] * 10,
        "Low": [100.0] * 10,
        "Close": [100.0] * 10,
        "Volume": [1000] * 10,
    }, index=dates)
    
    context = {
        "df": df,
        "rsi": pd.Series([50.0] * 10, index=dates),
        "macd": pd.DataFrame({"macd": [1.0] * 10, "signal": [1.0] * 10, "hist": [0.1] * 10}, index=dates),
        "bollinger": pd.DataFrame({"upper": [110.0] * 10, "mid": [100.0] * 10, "lower": [90.0] * 10}, index=dates),
        "cross_df": pd.DataFrame({"cross": ["none"] * 10}, index=dates),
        "vwap": pd.Series([98.0] * 10, index=dates),
        "econometrics": {"breaks": []},
    }
    
    events = compute_events(context)
    assert len(events) == 0


def test_rsi_events():
    """Verify RSI entry/exit zone events."""
    dates = pd.date_range("2026-01-01", periods=5)
    
    # 1. Entry Overbought: 65 -> 71
    context1 = {
        "rsi": pd.Series([50.0, 50.0, 50.0, 65.0, 71.0], index=dates)
    }
    ev1 = compute_events(context1)
    assert len(ev1) == 1
    assert ev1[0]["type"] == "rsi_zone_entry"
    assert ev1[0]["direction"] == "bullish"
    assert "overbought zone" in ev1[0]["detail"]
    
    # 2. Exit Overbought: 72 -> 68
    context2 = {
        "rsi": pd.Series([50.0, 50.0, 50.0, 72.0, 68.0], index=dates)
    }
    ev2 = compute_events(context2)
    assert len(ev2) == 1
    assert ev2[0]["type"] == "rsi_zone_exit"
    assert ev2[0]["direction"] == "bearish"
    assert "exited the overbought" in ev2[0]["detail"]

    # 3. Entry Oversold: 35 -> 28
    context3 = {
        "rsi": pd.Series([50.0, 50.0, 50.0, 35.0, 28.0], index=dates)
    }
    ev3 = compute_events(context3)
    assert len(ev3) == 1
    assert ev3[0]["type"] == "rsi_zone_entry"
    assert ev3[0]["direction"] == "bearish"
    assert "oversold zone" in ev3[0]["detail"]

    # 4. Exit Oversold: 28 -> 32
    context4 = {
        "rsi": pd.Series([50.0, 50.0, 50.0, 28.0, 32.0], index=dates)
    }
    ev4 = compute_events(context4)
    assert len(ev4) == 1
    assert ev4[0]["type"] == "rsi_zone_exit"
    assert ev4[0]["direction"] == "bullish"
    assert "exited the oversold" in ev4[0]["detail"]


def test_macd_hist_flip_events():
    """Verify MACD histogram sign flips."""
    dates = pd.date_range("2026-01-01", periods=5)
    
    # 1. Flip above zero: -0.1 -> 0.05
    context1 = {
        "macd": pd.DataFrame({"hist": [0.0, 0.0, 0.0, -0.1, 0.05]}, index=dates)
    }
    ev1 = compute_events(context1)
    assert len(ev1) == 1
    assert ev1[0]["type"] == "macd_hist_flip"
    assert ev1[0]["direction"] == "bullish"
    assert "crossed above zero" in ev1[0]["detail"]

    # 2. Flip below zero: 0.1 -> -0.05
    context2 = {
        "macd": pd.DataFrame({"hist": [0.0, 0.0, 0.0, 0.1, -0.05]}, index=dates)
    }
    ev2 = compute_events(context2)
    assert len(ev2) == 1
    assert ev2[0]["type"] == "macd_hist_flip"
    assert ev2[0]["direction"] == "bearish"
    assert "crossed below zero" in ev2[0]["detail"]


def test_ma_cross_today_events():
    """Verify SMA50/200 crossover events."""
    dates = pd.date_range("2026-01-01", periods=5)
    
    # Golden cross
    context1 = {
        "cross_df": pd.DataFrame({"cross": ["none", "none", "none", "none", "golden"]}, index=dates)
    }
    ev1 = compute_events(context1)
    assert len(ev1) == 1
    assert ev1[0]["type"] == "ma_cross_today"
    assert ev1[0]["direction"] == "bullish"
    assert "Golden Cross" in ev1[0]["detail"]

    # Death cross
    context2 = {
        "cross_df": pd.DataFrame({"cross": ["none", "none", "none", "none", "death"]}, index=dates)
    }
    ev2 = compute_events(context2)
    assert len(ev2) == 1
    assert ev2[0]["type"] == "ma_cross_today"
    assert ev2[0]["direction"] == "bearish"
    assert "Death Cross" in ev2[0]["detail"]


def test_bollinger_cross_events():
    """Verify Bollinger Bands crossover and re-entry events."""
    dates = pd.date_range("2026-01-01", periods=5)
    boll = pd.DataFrame({"upper": [110.0] * 5, "mid": [100.0] * 5, "lower": [90.0] * 5}, index=dates)
    
    # 1. Cross above upper band: 108 -> 112
    df1 = pd.DataFrame({"Close": [100.0, 100.0, 100.0, 108.0, 112.0]}, index=dates)
    ev1 = compute_events({"df": df1, "bollinger": boll})
    assert len(ev1) == 1
    assert ev1[0]["type"] == "bollinger_cross"
    assert ev1[0]["direction"] == "bullish"
    assert "crossed above the upper" in ev1[0]["detail"]

    # 2. Cross back below upper band: 112 -> 108
    df2 = pd.DataFrame({"Close": [100.0, 100.0, 100.0, 112.0, 108.0]}, index=dates)
    ev2 = compute_events({"df": df2, "bollinger": boll})
    assert len(ev2) == 1
    assert ev2[0]["type"] == "bollinger_cross"
    assert ev2[0]["direction"] == "bearish"
    assert "crossed back below" in ev2[0]["detail"]

    # 3. Cross below lower band: 92 -> 88
    df3 = pd.DataFrame({"Close": [100.0, 100.0, 100.0, 92.0, 88.0]}, index=dates)
    ev3 = compute_events({"df": df3, "bollinger": boll})
    assert len(ev3) == 1
    assert ev3[0]["type"] == "bollinger_cross"
    assert ev3[0]["direction"] == "bearish"
    assert "crossed below the lower" in ev3[0]["detail"]

    # 4. Cross back above lower band: 88 -> 92
    df4 = pd.DataFrame({"Close": [100.0, 100.0, 100.0, 88.0, 92.0]}, index=dates)
    ev4 = compute_events({"df": df4, "bollinger": boll})
    assert len(ev4) == 1
    assert ev4[0]["type"] == "bollinger_cross"
    assert ev4[0]["direction"] == "bullish"
    assert "crossed back above the lower" in ev4[0]["detail"]


def test_bollinger_cross_uses_current_band_not_previous_band():
    """Regression: a MOVING lower band must be compared against TODAY's value,
    not yesterday's. With a flat band the bug is invisible (prev_l == curr_l);
    here the band rises overnight, exposing the wrong-value comparison.
    """
    dates = pd.date_range("2026-01-01", periods=5)
    # Lower band rises from 88.0 (yesterday) to 91.0 (today).
    boll = pd.DataFrame(
        {"upper": [110.0] * 5, "mid": [100.0] * 5,
         "lower": [88.0, 88.0, 88.0, 88.0, 91.0]},
        index=dates,
    )
    # Price closed at 89.0 yesterday (above yesterday's band, 88.0) and rises
    # to 90.0 today -- but 90.0 is still BELOW today's band (91.0), so this
    # must NOT be reported as "crossed back above".
    df = pd.DataFrame({"Close": [100.0, 100.0, 100.0, 89.0, 90.0]}, index=dates)
    ev = compute_events({"df": df, "bollinger": boll})
    assert not any(e["type"] == "bollinger_cross" and e["direction"] == "bullish" for e in ev)


def test_range_52w_break_events_with_lookahead_guard():
    """Verify 52-week High/Low break events and assert no look-ahead.
    
    The high price of today must be compared to the previous 52-week High/Low
    excluding today (i.e. shifted by 1).
    """
    # Create 253 business days (50 weeks is 250 days, so 253 is enough for 52-week)
    dates = pd.date_range("2025-01-01", periods=254, freq="B")
    
    # 52-week High is 150.0 (placed at index 100). Rest of highs are 140.0.
    highs = [140.0] * 254
    highs[100] = 150.0
    
    # Today's high (last index 253) is 151.0.
    # The previous 52w High of yesterday (indices 0 to 252) is 150.0.
    # Since today's high (151.0) is greater than yesterday's 52w high (150.0), it is a breakout.
    # If look-ahead was bugged, today's high would be included in the rolling max,
    # so prev_high would be 151.0, and 151.0 > 151.0 would be False (no event).
    highs[253] = 151.0
    
    df = pd.DataFrame({
        "High": highs,
        "Low": [100.0] * 254,
        "Close": [120.0] * 254,
    }, index=dates)
    
    ev = compute_events({"df": df})
    assert len(ev) == 1
    assert ev[0]["type"] == "range_52w_break"
    assert ev[0]["direction"] == "bullish"
    assert "above the 52-week high of 150.00" in ev[0]["detail"]


def test_vwap_cross_events():
    """Verify crossing daily VWAP."""
    dates = pd.date_range("2026-01-01", periods=5)
    vwap = pd.Series([100.0] * 5, index=dates)
    
    # 1. Cross above: 99 -> 101
    df1 = pd.DataFrame({"Close": [100.0, 100.0, 100.0, 99.0, 101.0]}, index=dates)
    ev1 = compute_events({"df": df1, "vwap": vwap})
    assert len(ev1) == 1
    assert ev1[0]["type"] == "vwap_cross"
    assert ev1[0]["direction"] == "bullish"
    
    # 2. Cross below: 101 -> 99
    df2 = pd.DataFrame({"Close": [100.0, 100.0, 100.0, 101.0, 99.0]}, index=dates)
    ev2 = compute_events({"df": df2, "vwap": vwap})
    assert len(ev2) == 1
    assert ev2[0]["type"] == "vwap_cross"
    assert ev2[0]["direction"] == "bearish"


def test_structural_break_recent_events():
    """Verify structural breaks detected in the last 5 bars of the series."""
    dates = pd.date_range("2026-01-01", periods=10)
    df = pd.DataFrame({"Close": [100.0] * 10}, index=dates)
    
    # Break at index 7 (10 - 1 - 7 = 2 days ago < 5 days limit) -> recent
    context1 = {
        "df": df,
        "econometrics": {
            "breaks": [{"index": 7, "type": "mean_shift", "date": "2026-01-08"}]
        }
    }
    ev1 = compute_events(context1)
    assert len(ev1) == 1
    assert ev1[0]["type"] == "structural_break_recent"
    assert "mean_shift" in ev1[0]["detail"]

    # Break at index 2 (10 - 1 - 2 = 7 days ago >= 5 days limit) -> not recent
    context2 = {
        "df": df,
        "econometrics": {
            "breaks": [{"index": 2, "type": "mean_shift", "date": "2026-01-03"}]
        }
    }
    ev2 = compute_events(context2)
    assert len(ev2) == 0
