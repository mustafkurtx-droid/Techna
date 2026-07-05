"""Weekly Volume Profile indicator module.

Resamples daily price series to weekly and computes volume profile on weekly bars,
comparing the final daily close price to weekly boundaries.
"""
from __future__ import annotations

import pandas as pd

from techna.indicators.mtf import resample_to_weekly
from techna.indicators.volume_profile import compute_volume_profile


def compute_volume_profile_weekly(
    df: pd.DataFrame,
    lookback_weeks: int = 104,
    bins: int = 30,
    value_area: float = 0.70,
) -> dict:
    """Compute Volume Profile on weekly resampled bars.
    
    Returns:
        dict: Weekly volume profile metrics.
    """
    if df.empty:
        raise ValueError("df cannot be empty")
        
    for col in ("High", "Low", "Close", "Volume"):
        if col not in df.columns:
            raise ValueError(f"df must contain '{col}' column")
            
    # 1. Resample to weekly bars
    weekly_df = resample_to_weekly(df)
    
    if weekly_df.empty:
        return {
            "status": "warning",
            "poc_weekly": float("nan"),
            "vah_weekly": float("nan"),
            "val_weekly": float("nan"),
            "state_weekly": "unknown",
            "bins": [],
            "volumes": [],
            "weeks_used": 0,
            "warning": "Empty weekly dataset after resampling."
        }
        
    # 2. Slice last lookback_weeks
    weekly_sub = weekly_df.iloc[-lookback_weeks:] if len(weekly_df) >= lookback_weeks else weekly_df
    weeks_used = len(weekly_sub)
    
    status = "ok"
    warning_msg = None
    if len(weekly_df) < lookback_weeks:
        status = "warning"
        warning_msg = f"Insufficient history ({len(weekly_df)} weekly bars) for weekly volume profile lookback ({lookback_weeks}). Used all available weeks."
        
    # 3. Call compute_volume_profile engine on weekly subset
    res_vp = compute_volume_profile(weekly_sub, lookback=lookback_weeks, bins=bins, value_area_pct=value_area)
    
    poc_weekly = res_vp["poc"]
    vah_weekly = res_vp["vah"]
    val_weekly = res_vp["val"]
    bins_list = res_vp["bins"]
    volumes_list = res_vp["volumes"]
    
    # If the sub-VP engine had a warning or returned zero volumes
    if res_vp.get("status") == "warning":
        status = "warning"
        if "warning" in res_vp:
            warning_msg = res_vp["warning"]
            
    # 4. Compare final daily close price vs weekly VAH/VAL boundaries
    close_last = float(df["Close"].iloc[-1])
    if pd.isna(vah_weekly) or pd.isna(val_weekly):
        state_weekly = "unknown"
    elif close_last > vah_weekly:
        state_weekly = "above"
    elif close_last < val_weekly:
        state_weekly = "below"
    else:
        state_weekly = "inside"
        
    res = {
        "status": status,
        "poc_weekly": float(poc_weekly),
        "vah_weekly": float(vah_weekly),
        "val_weekly": float(val_weekly),
        "state_weekly": state_weekly,
        "bins": bins_list,
        "volumes": volumes_list,
        "weeks_used": int(weeks_used),
    }
    if warning_msg:
        res["warning"] = warning_msg
        
    return res
