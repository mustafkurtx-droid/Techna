"""Momentum indicators module.

Implements pure functions for computing Wilder Relative Strength Index (RSI),
Moving Average Convergence Divergence (MACD), and their respective states.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from techna import config


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Compute Relative Strength Index (RSI) using Wilder smoothing.
    
    The first period changes are averaged using simple moving average,
    and subsequent changes use Wilder recursive smoothing.
    
    Output range is [0, 100]. Warm-up period (first period rows) is NaN.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas.Series")
        
    if len(prices) <= period:
        # Return a series of all NaNs
        res = pd.Series(index=prices.index, dtype=float)
        return res
        
    delta = prices.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    
    avg_gain = pd.Series(index=prices.index, dtype=float)
    avg_loss = pd.Series(index=prices.index, dtype=float)
    
    # Calculate initial SMA for gain/loss
    avg_gain.iloc[period] = gain.iloc[1 : period + 1].mean()
    avg_loss.iloc[period] = loss.iloc[1 : period + 1].mean()
    
    alpha = 1.0 / period
    
    gain_arr = gain.values
    loss_arr = loss.values
    avg_gain_arr = avg_gain.values
    avg_loss_arr = avg_loss.values
    
    for i in range(period + 1, len(prices)):
        avg_gain_arr[i] = avg_gain_arr[i - 1] * (1.0 - alpha) + gain_arr[i] * alpha
        avg_loss_arr[i] = avg_loss_arr[i - 1] * (1.0 - alpha) + loss_arr[i] * alpha
        
    avg_gain = pd.Series(avg_gain_arr, index=prices.index)
    avg_loss = pd.Series(avg_loss_arr, index=prices.index)
    
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs.fillna(0.0)))
    
    # Handle NaNs and division by zero
    rsi = rsi.where(avg_loss.notna(), np.nan)
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    
    return rsi


def compute_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Compute MACD, Signal Line, and MACD Histogram.
    
    Using standard EMA (adjust=False).
    
    Returns:
        pd.DataFrame: Columns are "macd", "signal", "hist".
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas.Series")
        
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    
    res = pd.DataFrame(index=prices.index)
    res["macd"] = macd_line
    res["signal"] = signal_line
    res["hist"] = hist
    return res


def rsi_state(value: pd.Series | float) -> str:
    """Classify RSI state.
    
    - "overbought": >= 70
    - "oversold": <= 30
    - "neutral": any other value (or NaN)
    """
    val = value.iloc[-1] if isinstance(value, pd.Series) else value
    if pd.isna(val):
        return "neutral"
    if val >= config.RSI_OVERBOUGHT:
        return "overbought"
    elif val <= config.RSI_OVERSOLD:
        return "oversold"
    else:
        return "neutral"


def macd_state(hist: pd.Series | float) -> str:
    """Classify MACD state from the histogram (hist = macd - signal).

    The sign of the histogram fully determines the state, so only `hist` is
    needed (hist > 0 is exactly macd > signal).

    - "bullish": hist > 0
    - "bearish": hist <= 0 (or NaN)
    """
    h = hist.iloc[-1] if isinstance(hist, pd.Series) else hist
    if pd.isna(h):
        return "bearish"
    if h > 0.0:
        return "bullish"
    else:
        return "bearish"


def compute_stochastic(
    df: pd.DataFrame,
    k_period: int = 14,
    smooth_k: int = 3,
    d_period: int = 3,
) -> pd.DataFrame:
    """Compute Slow Stochastic %K and %D.
    
    Returns:
        pd.DataFrame: Columns are "slow_k", "slow_d".
    """
    if df.empty:
        raise ValueError("df cannot be empty")
        
    for col in ("High", "Low", "Close"):
        if col not in df.columns:
            raise ValueError(f"df must contain '{col}' column")
            
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    
    ll = low.rolling(window=k_period, min_periods=k_period).min()
    hh = high.rolling(window=k_period, min_periods=k_period).max()
    
    diff = hh - ll
    raw_k = 100 * (close - ll) / diff.replace(0.0, float("nan"))
    
    slow_k = raw_k.rolling(window=smooth_k, min_periods=smooth_k).mean()
    slow_d = slow_k.rolling(window=d_period, min_periods=d_period).mean()
    
    res = pd.DataFrame(index=df.index)
    res["slow_k"] = slow_k
    res["slow_d"] = slow_d
    return res


def stochastic_state(k_value: pd.Series | float) -> str:
    """Classify Stochastic slow_k state.
    
    - "overbought": >= 80
    - "oversold": <= 20
    - "neutral": any other value (or NaN)
    """
    val = k_value.iloc[-1] if isinstance(k_value, pd.Series) else k_value
    if pd.isna(val):
        return "neutral"
    if val >= config.STOCH_OVERBOUGHT:
        return "overbought"
    elif val <= config.STOCH_OVERSOLD:
        return "oversold"
    else:
        return "neutral"
