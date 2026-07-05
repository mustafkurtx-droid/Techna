"""Volume Profile (VP) indicator module.

Computes Point of Control (POC), Value Area High (VAH) and Value Area Low (VAL)
based on distributed historical bar volumes.
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def compute_volume_profile(
    df: pd.DataFrame,
    lookback: int = 252,
    bins: int = 30,
    value_area_pct: float = 0.70,
) -> dict:
    """Compute Volume Profile and Value Area based on distributed volume.
    
    Returns:
        dict: Volume profile metrics.
    """
    if df.empty:
        raise ValueError("df cannot be empty")
        
    for col in ("High", "Low", "Close", "Volume"):
        if col not in df.columns:
            raise ValueError(f"df must contain '{col}' column")
            
    # Son lookback bar alınır (daha azsa hepsi + warning)
    sub_df = df.iloc[-lookback:] if len(df) >= lookback else df
    lookback_used = len(sub_df)
    
    status = "ok"
    warning_msg = None
    if len(df) < lookback:
        status = "warning"
        warning_msg = f"Insufficient history ({len(df)} bars) for full volume profile lookback ({lookback}). Used all available bars."
        
    high = sub_df["High"]
    low = sub_df["Low"]
    close = sub_df["Close"]
    volume = sub_df["Volume"]
    
    min_low = float(low.min())
    max_high = float(high.max())
    
    # Flat price history edge case
    if min_low == max_high:
        poc_price = min_low
        vah = min_low
        val = min_low
        state_val = "inside"
        
        # Write volume to a single bin
        volumes_list = [float(volume.sum())] + [0.0] * (bins - 1)
        bin_edges = [min_low] * (bins + 1)
        
        return {
            "status": status,
            "poc": float(poc_price),
            "vah": float(vah),
            "val": float(val),
            "state": state_val,
            "bins": bin_edges,
            "volumes": volumes_list,
            "lookback_used": lookback_used,
            "warning": warning_msg if warning_msg else "Flat price history detected."
        }
        
    edges = np.linspace(min_low, max_high, bins + 1)
    volumes = np.zeros(bins, dtype=float)
    
    # Distribute volume for each bar
    for idx in range(len(sub_df)):
        b_low = float(low.iloc[idx])
        b_high = float(high.iloc[idx])
        b_vol = float(volume.iloc[idx])
        
        if pd.isna(b_low) or pd.isna(b_high) or pd.isna(b_vol):
            continue
            
        if b_low == b_high:
            # Single price bar: allocate 100% to the containing bin
            k = int(np.clip(np.digitize(b_low, edges) - 1, 0, bins - 1))
            volumes[k] += b_vol
        else:
            # Distribute proportionally based on overlap
            b_width = b_high - b_low
            for k in range(bins):
                lower_edge = edges[k]
                upper_edge = edges[k+1]
                overlap = max(0.0, min(b_high, upper_edge) - max(b_low, lower_edge))
                if overlap > 0.0:
                    volumes[k] += b_vol * (overlap / b_width)
                    
    total_volume = volumes.sum()
    
    if total_volume == 0:
        poc_price = (min_low + max_high) / 2.0
        vah = max_high
        val = min_low
        state_val = "inside"
        
        return {
            "status": status,
            "poc": float(poc_price),
            "vah": float(vah),
            "val": float(val),
            "state": state_val,
            "bins": edges.tolist(),
            "volumes": volumes.tolist(),
            "lookback_used": lookback_used,
            "warning": warning_msg if warning_msg else "Zero total volume in the period."
        }
        
    # 4. POC calculation: center of highest volume bin. Tie-break: highest price wins.
    max_vol = volumes.max()
    poc_bin_idx = max(k for k in range(bins) if volumes[k] == max_vol)
    poc_price = (edges[poc_bin_idx] + edges[poc_bin_idx+1]) / 2.0
    
    # 5. Value Area (%70) Expansion:
    left_idx = poc_bin_idx
    right_idx = poc_bin_idx
    current_va_volume = volumes[poc_bin_idx]
    target_volume = value_area_pct * total_volume
    
    while current_va_volume < target_volume:
        can_expand_above = (right_idx + 1 < bins)
        can_expand_below = (left_idx - 1 >= 0)
        
        if not can_expand_above and not can_expand_below:
            break
            
        if can_expand_above and can_expand_below:
            vol_above = volumes[right_idx + 1]
            vol_below = volumes[left_idx - 1]
            if vol_above >= vol_below:  # >= resolves tie in favor of upper (eşitlikte üst)
                right_idx += 1
                current_va_volume += vol_above
            else:
                left_idx -= 1
                current_va_volume += vol_below
        elif can_expand_above:
            right_idx += 1
            current_va_volume += volumes[right_idx]
        else:
            left_idx -= 1
            current_va_volume += volumes[left_idx]
            
    vah = float(edges[right_idx + 1])
    val = float(edges[left_idx])
    
    # 6. Determine state relative to Value Area
    close_last = float(close.iloc[-1])
    if close_last > vah:
        state_val = "above"
    elif close_last < val:
        state_val = "below"
    else:
        state_val = "inside"
        
    res = {
        "status": status,
        "poc": float(poc_price),
        "vah": float(vah),
        "val": float(val),
        "state": state_val,
        "bins": edges.tolist(),
        "volumes": volumes.tolist(),
        "lookback_used": lookback_used,
    }
    if warning_msg:
        res["warning"] = warning_msg
        
    return res
