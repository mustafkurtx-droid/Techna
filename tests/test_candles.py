"""Unit tests for daily candlestick pattern detection and events."""
from __future__ import annotations

import pandas as pd

from techna.indicators.candles import compute_candle_patterns
from techna.indicators.events import compute_events


def test_doji_detection():
    """Verify Doji detection logic."""
    dates = pd.date_range("2026-01-01", periods=3)
    
    # 1. Doji: flat Open/Close, large range
    df = pd.DataFrame({
        "Open": [100.0, 100.0, 100.0],
        "High": [105.0, 105.0, 105.0],
        "Low": [95.0, 95.0, 95.0],
        "Close": [100.0, 100.1, 100.0],
    }, index=dates)
    
    res = compute_candle_patterns(df)
    assert res["doji"].iloc[0]
    assert res["doji"].iloc[1]  # body = 0.1, range = 10, body/range = 0.01 <= 0.1
    assert res["doji"].iloc[2]


def _context_bars(start: float, step: float, n: int = 12) -> dict:
    """Flat-bodied bars whose closes move by `step` each bar -- a clean
    downtrend (step<0) or uptrend (step>0) context for pattern bars."""
    closes = [start + step * i for i in range(n)]
    return {
        "Open": [x + 0.1 for x in closes],
        "High": [x + 0.2 for x in closes],
        "Low": [x - 0.2 for x in closes],
        "Close": closes,
    }


def test_hammer_requires_downtrend_context():
    """Hammer shape only counts after a 10-bar DOWNTREND (frozen rule)."""
    # 12 declining context bars, then a hammer-shaped bar:
    # Open=91.0, Close=91.5 (body=0.5), Low=90.0 (lower shadow=1.0 >= 2*body),
    # High=91.6 (upper shadow=0.1 <= 0.3*body=0.15).
    ctx = _context_bars(100.0, -0.8)
    data = {k: v + [x] for (k, v), x in zip(ctx.items(), [91.0, 91.6, 90.0, 91.5])}
    df = pd.DataFrame(data, index=pd.date_range("2026-01-01", periods=13))

    res = compute_candle_patterns(df)
    assert res["hammer"].iloc[-1]
    assert not res["shooting_star"].iloc[-1]

    # SAME shape in an UPTREND context must NOT be a hammer.
    ctx_up = _context_bars(80.0, +0.8)
    data_up = {k: v + [x] for (k, v), x in zip(ctx_up.items(), [91.0, 91.6, 90.0, 91.5])}
    df_up = pd.DataFrame(data_up, index=pd.date_range("2026-01-01", periods=13))
    assert not compute_candle_patterns(df_up)["hammer"].iloc[-1]


def test_shooting_star_requires_uptrend_context():
    """Shooting star shape only counts after a 10-bar UPTREND (frozen rule)."""
    # 12 rising context bars, then a star-shaped bar:
    # Open=100.0, Close=99.5 (body=0.5), High=101.5 (upper shadow=1.5 >= 2*body),
    # Low=99.4 (lower shadow=0.1 <= 0.3*body=0.15).
    ctx = _context_bars(90.0, +0.8)
    data = {k: v + [x] for (k, v), x in zip(ctx.items(), [100.0, 101.5, 99.4, 99.5])}
    df = pd.DataFrame(data, index=pd.date_range("2026-01-01", periods=13))

    res = compute_candle_patterns(df)
    assert res["shooting_star"].iloc[-1]
    assert not res["hammer"].iloc[-1]

    # SAME shape in a DOWNTREND context must NOT be a shooting star.
    ctx_dn = _context_bars(110.0, -0.8)
    data_dn = {k: v + [x] for (k, v), x in zip(ctx_dn.items(), [100.0, 101.5, 99.4, 99.5])}
    df_dn = pd.DataFrame(data_dn, index=pd.date_range("2026-01-01", periods=13))
    assert not compute_candle_patterns(df_dn)["shooting_star"].iloc[-1]


def test_hammer_upper_shadow_tolerance_is_30pct():
    """Upper shadow up to 0.30*body is allowed (frozen threshold), above it is not."""
    ctx = _context_bars(100.0, -0.8)
    # body=1.0, lower shadow=2.5, upper shadow=0.29 -> hammer.
    ok = {k: v + [x] for (k, v), x in zip(ctx.items(), [91.0, 92.29, 88.5, 92.0])}
    df_ok = pd.DataFrame(ok, index=pd.date_range("2026-01-01", periods=13))
    assert compute_candle_patterns(df_ok)["hammer"].iloc[-1]

    # Identical but upper shadow=0.35 > 0.30*body -> NOT a hammer.
    bad = {k: v + [x] for (k, v), x in zip(ctx.items(), [91.0, 92.35, 88.5, 92.0])}
    df_bad = pd.DataFrame(bad, index=pd.date_range("2026-01-01", periods=13))
    assert not compute_candle_patterns(df_bad)["hammer"].iloc[-1]


def test_engulfing_patterns():
    """Verify Bullish and Bearish Engulfing detection logic."""
    dates = pd.date_range("2026-01-01", periods=3)
    
    # Bullish Engulfing:
    # prev bearish: Close=95, Open=100 (bearish body = 5)
    # curr bullish: Close=102, Open=94 (bullish body = 8)
    # body_curr (8) > body_prev (5)
    # engulfs: open_curr (94) <= close_prev (95) and close_curr (102) > open_prev (100)
    df_bull = pd.DataFrame({
        "Open": [100.0, 94.0, 100.0],
        "High": [101.0, 103.0, 100.0],
        "Low": [94.0, 93.0, 100.0],
        "Close": [95.0, 102.0, 100.0],
    }, index=dates)
    
    res_bull = compute_candle_patterns(df_bull)
    assert res_bull["bullish_engulfing"].iloc[1]
    
    # Bearish Engulfing:
    # prev bullish: Close=100, Open=95 (bullish body = 5)
    # curr bearish: Close=94, Open=101 (bearish body = 7)
    # body_curr (7) > body_prev (5)
    # engulfs: open_curr (101) >= close_prev (100) and close_curr (94) < open_prev (95)
    df_bear = pd.DataFrame({
        "Open": [95.0, 101.0, 100.0],
        "High": [101.0, 102.0, 100.0],
        "Low": [94.0, 93.0, 100.0],
        "Close": [100.0, 94.0, 100.0],
    }, index=dates)
    
    res_bear = compute_candle_patterns(df_bear)
    assert res_bear["bearish_engulfing"].iloc[1]


def test_candle_pattern_events():
    """Verify events trigger correctly when patterns are active on last bar."""
    dates = pd.date_range("2026-01-01", periods=2)
    
    context = {
        "candles": {
            "status": "ok",
            "patterns": {
                "doji": pd.Series([False, True], index=dates),
                "hammer": pd.Series([False, False], index=dates),
                "shooting_star": pd.Series([False, False], index=dates),
                "bullish_engulfing": pd.Series([False, True], index=dates),
                "bearish_engulfing": pd.Series([False, False], index=dates),
            }
        }
    }
    
    ev = compute_events(context)
    # Should trigger both Doji and Bullish Engulfing events
    assert len(ev) == 2
    types = [e["type"] for e in ev]
    assert all(t == "candle_pattern_detected" for t in types)
    
    directions = [e["direction"] for e in ev]
    assert "neutral" in directions
    assert "bullish" in directions
