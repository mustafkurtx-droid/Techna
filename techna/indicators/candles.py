"""Candlestick Pattern detection module.

Implements detection for Doji, Hammer, Shooting Star, Bullish Engulfing, and Bearish Engulfing.
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def compute_candle_patterns(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Detect daily candlestick patterns.
    
    Returns:
        dict[str, pd.Series]: Boolean series mapping for each pattern.
    """
    if df.empty:
        raise ValueError("df cannot be empty")
        
    for col in ("Open", "High", "Low", "Close"):
        if col not in df.columns:
            raise ValueError(f"df must contain '{col}' column")
            
    o = df["Open"]
    h = df["High"]
    low_val = df["Low"]
    c = df["Close"]
    
    body = (c - o).abs()
    total_range = h - low_val

    # Shadows
    upper_shadow = h - np.maximum(o, c)
    lower_shadow = np.minimum(o, c) - low_val

    # Context slope: least-squares slope of the 10 closes ENDING AT THE
    # PREVIOUS bar (the pattern bar itself is excluded). A hammer without a
    # preceding downtrend -- or a shooting star without a preceding uptrend --
    # is noise, not a pattern (frozen rule, see BUILD_ROADMAP). Bars without
    # 10 prior closes get NaN, and NaN comparisons are False, so early bars
    # can never match these two context-dependent patterns.
    x10 = np.arange(10, dtype=float)
    context_slope = c.rolling(window=10, min_periods=10).apply(
        lambda vals: np.polyfit(x10, vals, 1)[0], raw=True
    ).shift(1)

    # 1. Doji: body <= 10% of total range, total range > 0
    doji = (body <= 0.1 * total_range) & (total_range > 0)

    # 2. Hammer: lower shadow >= 2x body, upper shadow <= 30% of body,
    #    body > 0, total range > 0, and a DOWNTREND context (slope < 0)
    hammer = (
        (lower_shadow >= 2.0 * body) & (upper_shadow <= 0.3 * body)
        & (body > 0) & (total_range > 0) & (context_slope < 0)
    )

    # 3. Shooting Star: upper shadow >= 2x body, lower shadow <= 30% of body,
    #    body > 0, total range > 0, and an UPTREND context (slope > 0)
    shooting_star = (
        (upper_shadow >= 2.0 * body) & (lower_shadow <= 0.3 * body)
        & (body > 0) & (total_range > 0) & (context_slope > 0)
    )
    
    # 4. Bullish Engulfing (2-bar)
    # prev bar was bearish (close < open)
    # curr bar is bullish (close > open)
    # curr body engulfs prev body (open_curr <= close_prev and close_curr > open_prev)
    # curr body is strictly larger than prev body
    prev_close = c.shift(1)
    prev_open = o.shift(1)
    prev_body = body.shift(1)
    
    prev_bearish = prev_close < prev_open
    curr_bullish = c > o
    engulfs_bullish = (o <= prev_close) & (c > prev_open) & (body > prev_body)
    bullish_engulfing = prev_bearish & curr_bullish & engulfs_bullish
    
    # 5. Bearish Engulfing (2-bar)
    # prev bar was bullish (close > open)
    # curr bar is bearish (close < open)
    # curr body engulfs prev body (open_curr >= close_prev and close_curr < open_prev)
    # curr body is strictly larger than prev body
    prev_bullish = prev_close > prev_open
    curr_bearish = c < o
    engulfs_bearish = (o >= prev_close) & (c < prev_open) & (body > prev_body)
    bearish_engulfing = prev_bullish & curr_bearish & engulfs_bearish
    
    return {
        "doji": doji,
        "hammer": hammer,
        "shooting_star": shooting_star,
        "bullish_engulfing": bullish_engulfing,
        "bearish_engulfing": bearish_engulfing,
    }
