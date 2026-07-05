"""Bollinger Squeeze indicator module.

Detects volatility compression by comparing Bollinger Bands with Keltner Channels.
"""
from __future__ import annotations

import pandas as pd

from techna.indicators import compute_bollinger, compute_ema, compute_atr


def compute_squeeze(
    df: pd.DataFrame,
    period: int = 20,
    bb_mult: float = 2.0,
    kc_mult: float = 1.5,
) -> dict:
    """Compute Bollinger Squeeze and Keltner Channels.
    
    Returns:
        dict: Squeeze metrics.
    """
    if df.empty:
        raise ValueError("df cannot be empty")
        
    for col in ("High", "Low", "Close", "Volume"):
        if col not in df.columns:
            raise ValueError(f"df must contain '{col}' column")
            
    close = df["Close"]
    
    # 1. Bollinger Bands
    bb = compute_bollinger(close, window=period, num_std=bb_mult)
    upper_bb = bb["upper"]
    lower_bb = bb["lower"]
    
    # 2. Keltner Channels
    middle_kc = compute_ema(close, span=period)
    atr = compute_atr(df, period=period)
    upper_kc = middle_kc + kc_mult * atr
    lower_kc = middle_kc - kc_mult * atr
    
    # 3. Squeeze state Series: Bollinger Bands completely inside Keltner Channels
    # (lower_bb > lower_kc) & (upper_bb < upper_kc)
    # Check for NaNs to prevent false signals on missing history
    has_history = upper_bb.notna() & lower_bb.notna() & upper_kc.notna() & lower_kc.notna()
    squeeze_active = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    squeeze_active = squeeze_active.where(has_history, False)
    
    # 4. Squeeze value Series
    # (upper_bb - lower_bb) / (upper_kc - lower_kc)
    bb_width = upper_bb - lower_bb
    kc_width = upper_kc - lower_kc
    squeeze_value = bb_width / kc_width.replace(0.0, float("nan"))
    squeeze_value = squeeze_value.where(has_history, float("nan"))
    
    # 5. Squeeze duration: consecutive active count backwards from the last bar
    duration = 0
    if len(squeeze_active) > 0 and squeeze_active.iloc[-1]:
        for val in reversed(squeeze_active.values):
            if pd.isna(val):
                break
            if val:
                duration += 1
            else:
                break
                
    status = "ok"
    warning_msg = None
    if len(df) < period:
        status = "warning"
        warning_msg = f"Insufficient history ({len(df)} bars) for Bollinger Squeeze calculation (period={period})."
        
    res = {
        "status": status,
        "squeeze_active": bool(squeeze_active.iloc[-1]) if len(squeeze_active) > 0 else False,
        "squeeze_value": float(squeeze_value.iloc[-1]) if len(squeeze_value) > 0 and not pd.isna(squeeze_value.iloc[-1]) else float("nan"),
        "squeeze_duration": int(duration),
        "_squeeze_active_series": squeeze_active,
    }
    if warning_msg:
        res["warning"] = warning_msg
        
    return res
