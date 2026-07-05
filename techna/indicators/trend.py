"""Trend indicators module.

Implements pure functions for computing Simple Moving Average (SMA),
Exponential Moving Average (EMA), golden/death crosses, and trend states.
No file/network I/O is allowed here.
"""
from __future__ import annotations

import pandas as pd


def compute_sma(prices: pd.Series, window: int) -> pd.Series:
    """Compute Simple Moving Average (SMA) with the specified window.
    
    First window - 1 values are NaN (warm-up).
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas.Series")
    return prices.rolling(window=window, min_periods=window).mean()


def compute_ema(prices: pd.Series, span: int) -> pd.Series:
    """Compute Exponential Moving Average (EMA) with the specified span.
    
    Uses adjust=False for the standard recursive formula where the first
    non-NaN price serves as the seed.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas.Series")
    return prices.ewm(span=span, adjust=False).mean()


def detect_cross(fast: pd.Series, slow: pd.Series) -> pd.DataFrame:
    """Detect crossovers between fast and slow series.
    
    A cross is detected on the bar where fast - slow changes sign.
    - Golden cross: fast crosses above slow (prev_diff < 0, curr_diff > 0)
    - Death cross: fast crosses below slow (prev_diff > 0, curr_diff < 0)
    
    Only evaluates when both fast and slow values are non-NaN for both the
    current and the previous bar.
    
    Returns:
        pd.DataFrame: A DataFrame with the same index as the input, containing:
            - "cross": "golden", "death", or "none"
    """
    if not isinstance(fast, pd.Series) or not isinstance(slow, pd.Series):
        raise TypeError("fast and slow must be pandas.Series")
    
    res = pd.DataFrame(index=fast.index)
    res["cross"] = "none"
    
    diff = fast - slow
    prev_diff = diff.shift(1)
    
    # Valid rows are where both current diff and previous diff are non-NaN
    valid = diff.notna() & prev_diff.notna()
    
    res.loc[valid & (prev_diff < 0) & (diff > 0), "cross"] = "golden"
    res.loc[valid & (prev_diff > 0) & (diff < 0), "cross"] = "death"
    
    return res


def trend_state(
    prices: pd.Series | float,
    sma50: pd.Series | float,
    sma200: pd.Series | float,
) -> str:
    """Classify the trend alignment based on price, SMA50, and SMA200.
    
    - "uptrend": price > SMA200 and SMA50 > SMA200
    - "downtrend": price < SMA200 and SMA50 < SMA200
    - "sideways": any other configuration (or if any input is NaN)
    """
    p = prices.iloc[-1] if isinstance(prices, pd.Series) else prices
    s50 = sma50.iloc[-1] if isinstance(sma50, pd.Series) else sma50
    s200 = sma200.iloc[-1] if isinstance(sma200, pd.Series) else sma200
    
    if pd.isna(p) or pd.isna(s50) or pd.isna(s200):
        return "sideways"
        
    if p > s200 and s50 > s200:
        return "uptrend"
    elif p < s200 and s50 < s200:
        return "downtrend"
    else:
        return "sideways"
