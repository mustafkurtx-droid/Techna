"""Fibonacci Retracement and touch respect indicator module.

Calculates static retracement levels and measures empirical respect using historical base rates.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from techna import config
from techna.indicators.regime import compute_atr
from techna.indicators.baserates import forward_return, conditional_stats


def compute_fibonacci(
    df: pd.DataFrame,
    lookback: int = 252,
    levels: list[float] = [0.236, 0.382, 0.5, 0.618, 0.786],
    touch_atr_mult: float = 0.25,
) -> dict:
    """Compute Fibonacci retracement levels and touch respect stats.
    
    Returns:
        dict: Fibonacci results.
    """
    if df.empty:
        raise ValueError("df cannot be empty")
        
    for col in ("High", "Low", "Close"):
        if col not in df.columns:
            raise ValueError(f"df must contain '{col}' column")
            
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    
    # 1. Determine swing
    sub_df = df.iloc[-lookback:] if len(df) >= lookback else df
    high_sub = sub_df["High"]
    low_sub = sub_df["Low"]
    
    swing_high_val = float(high_sub.max())
    swing_low_val = float(low_sub.min())
    swing_high_idx = high_sub.idxmax()
    swing_low_idx = low_sub.idxmin()
    
    status = "ok"
    warnings_list = []
    direction = "none"
    
    if len(df) < lookback:
        status = "warning"
        warnings_list.append(f"Insufficient history ({len(df)} bars) for full Fibonacci lookback ({lookback}). Used all available bars.")
        
    if swing_high_idx == swing_low_idx or swing_high_val == swing_low_val:
        status = "warning"
        warnings_list.append("Flat price history or overlapping swings detected; levels are collapsed.")
        direction = "none"
        levels_dict = {lvl: swing_high_val for lvl in levels}
    elif swing_high_idx > swing_low_idx:
        direction = "up"
        levels_dict = {
            lvl: swing_high_val - lvl * (swing_high_val - swing_low_val) for lvl in levels
        }
    else:
        direction = "down"
        levels_dict = {
            lvl: swing_low_val + lvl * (swing_high_val - swing_low_val) for lvl in levels
        }
        
    # 2. Touch respect test
    # Compute ATR14 for the entire dataframe
    atr = compute_atr(df, period=14)
    fwd_ret = forward_return(close, 10)
    
    respect_stats = {}
    for lvl in levels:
        level_price = levels_dict[lvl]
        touches = pd.Series(False, index=df.index)
        
        for i in range(1, len(df)):
            atr_val = atr.iloc[i]
            if pd.isna(atr_val) or atr_val <= 0:
                continue
                
            band_half = touch_atr_mult * atr_val
            lower_band = level_price - band_half
            upper_band = level_price + band_half
            
            curr_high = high.iloc[i]
            curr_low = low.iloc[i]
            prev_high = high.iloc[i-1]
            prev_low = low.iloc[i-1]
            
            # Entry into band
            overlaps = (curr_high >= lower_band) and (curr_low <= upper_band)
            prev_outside = (prev_high < lower_band) or (prev_low > upper_band)
            
            if overlaps and prev_outside:
                touches.iloc[i] = True
                
        # Compute conditional stats for this level's touches
        stats = conditional_stats(touches, fwd_ret, min_sample=config.BASE_RATE_MIN_SAMPLE)
        respect_stats[lvl] = {
            "n": int(stats["n"]),
            "mean": float(stats["mean"]) if not np.isnan(stats["mean"]) else float("nan"),
            "win_rate": float(stats["win_rate"]) if not np.isnan(stats["win_rate"]) else float("nan"),
            "reliable": bool(stats["reliable"]),
        }
        
    # 3. Determine state relative to current price
    close_last = float(close.iloc[-1])
    # Identify which levels the price is currently between
    sorted_levels = sorted([(lvl, price) for lvl, price in levels_dict.items()], key=lambda x: x[1])
    
    lower_lvl = None
    upper_lvl = None
    for idx in range(len(sorted_levels) - 1):
        lvl_a, pr_a = sorted_levels[idx]
        lvl_b, pr_b = sorted_levels[idx+1]
        if pr_a <= close_last <= pr_b:
            lower_lvl = (lvl_a, pr_a)
            upper_lvl = (lvl_b, pr_b)
            break
            
    res = {
        "status": status,
        "swing_high": swing_high_val,
        "swing_low": swing_low_val,
        "direction": direction,
        "levels": levels_dict,
        "close_last": close_last,
        "respect_stats": respect_stats,
        "current_position": {
            "lower_level": lower_lvl[0] if lower_lvl else None,
            "lower_price": lower_lvl[1] if lower_lvl else None,
            "upper_level": upper_lvl[0] if upper_lvl else None,
            "upper_price": upper_lvl[1] if upper_lvl else None,
        },
    }
    if warnings_list:
        res["warning"] = "; ".join(warnings_list)
        
    return res
