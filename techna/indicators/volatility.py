"""Volatility indicators module (Bollinger Bands).

Implements Bollinger Bands calculation and state classification.
"""
from __future__ import annotations

import pandas as pd


def compute_bollinger(
    prices: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """Compute Bollinger Bands (mid, upper, lower, pct_b, bandwidth).
    
    Uses population standard deviation (ddof=0).
    
    Returns:
        pd.DataFrame: Columns are "mid", "upper", "lower", "pct_b", "bandwidth".
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas.Series")
        
    mid = prices.rolling(window=window, min_periods=window).mean()
    std = prices.rolling(window=window, min_periods=window).std(ddof=0)
    
    upper = mid + num_std * std
    lower = mid - num_std * std
    
    diff = upper - lower
    # Safe division for pct_b and bandwidth
    pct_b = (prices - lower) / diff.replace(0.0, float("nan"))
    # If upper == lower (std = 0), pct_b could be defined as 0.5 or NaN. Let's fill NaN with 0.5 if price is exactly at mid.
    pct_b = pct_b.fillna(0.5).where(diff.notna(), float("nan"))
    
    bandwidth = diff / mid.replace(0.0, float("nan"))
    bandwidth = bandwidth.where(mid.notna(), float("nan"))
    
    res = pd.DataFrame(index=prices.index)
    res["mid"] = mid
    res["upper"] = upper
    res["lower"] = lower
    res["pct_b"] = pct_b
    res["bandwidth"] = bandwidth
    return res


def bollinger_state(
    price: pd.Series | float,
    upper: pd.Series | float,
    mid: pd.Series | float,
    lower: pd.Series | float,
) -> str:
    """Classify price position relative to Bollinger Bands.
    
    - "above_upper": price > upper
    - "below_lower": price < lower
    - "within_bands": price is between upper and lower (or if any input is NaN)
    """
    p = price.iloc[-1] if isinstance(price, pd.Series) else price
    u = upper.iloc[-1] if isinstance(upper, pd.Series) else upper
    lo = lower.iloc[-1] if isinstance(lower, pd.Series) else lower

    if pd.isna(p) or pd.isna(u) or pd.isna(lo):
        return "within_bands"

    if p > u:
        return "above_upper"
    elif p < lo:
        return "below_lower"
    else:
        return "within_bands"
