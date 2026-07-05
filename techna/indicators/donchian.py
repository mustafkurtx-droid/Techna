"""Donchian Channels indicator module.

Computes upper, lower, and middle bands for 20-day and 55-day channels.
"""
from __future__ import annotations

import pandas as pd


def compute_donchian(
    df: pd.DataFrame,
    fast: int = 20,
    slow: int = 55,
) -> pd.DataFrame:
    """Compute Donchian Channels (fast and slow periods).
    
    Returns:
        pd.DataFrame: Columns are:
            "upper_20", "lower_20", "mid_20", "pos_pct_20",
            "upper_55", "lower_55", "mid_55", "pos_pct_55"
    """
    if df.empty:
        raise ValueError("df cannot be empty")
        
    for col in ("High", "Low", "Close"):
        if col not in df.columns:
            raise ValueError(f"df must contain '{col}' column")
            
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # Channels EXCLUDE the current bar (shift(1)): today's high must not lift
    # today's own band, otherwise a breakout above the channel is impossible
    # by construction (look-ahead). Frozen convention -- see BUILD_ROADMAP.
    # Fast Channel (20)
    upper_20 = high.rolling(window=fast).max().shift(1)
    lower_20 = low.rolling(window=fast).min().shift(1)
    mid_20 = (upper_20 + lower_20) / 2.0
    diff_20 = upper_20 - lower_20
    pos_pct_20 = 100.0 * (close - lower_20) / diff_20.replace(0.0, float("nan"))

    # Slow Channel (55)
    upper_55 = high.rolling(window=slow).max().shift(1)
    lower_55 = low.rolling(window=slow).min().shift(1)
    mid_55 = (upper_55 + lower_55) / 2.0
    diff_55 = upper_55 - lower_55
    pos_pct_55 = 100.0 * (close - lower_55) / diff_55.replace(0.0, float("nan"))
    
    res = pd.DataFrame(index=df.index)
    res["upper_20"] = upper_20
    res["lower_20"] = lower_20
    res["mid_20"] = mid_20
    res["pos_pct_20"] = pos_pct_20
    
    res["upper_55"] = upper_55
    res["lower_55"] = lower_55
    res["mid_55"] = mid_55
    res["pos_pct_55"] = pos_pct_55
    
    return res
