"""Volume indicators module.

Provides OBV (On-Balance Volume), OBV Divergence, and VWAP (Volume Weighted Average Price) approximation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from techna import config


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Calculate On-Balance Volume (OBV)."""
    if not isinstance(close, pd.Series) or not isinstance(volume, pd.Series):
        raise TypeError("close and volume must be pandas Series")
    if not close.index.equals(volume.index) or len(close) != len(volume):
        raise ValueError("close and volume must have matching indexes and lengths")
        
    if len(close) == 0:
        return pd.Series(dtype=float, name="OBV")
        
    close_arr = close.values
    volume_arr = volume.values
    obv_arr = np.zeros(len(close))
    
    obv_arr[0] = 0.0
    for i in range(1, len(close_arr)):
        if close_arr[i] > close_arr[i - 1]:
            obv_arr[i] = obv_arr[i - 1] + volume_arr[i]
        elif close_arr[i] < close_arr[i - 1]:
            obv_arr[i] = obv_arr[i - 1] - volume_arr[i]
        else:
            obv_arr[i] = obv_arr[i - 1]
            
    return pd.Series(obv_arr, index=close.index, name="OBV")


def detect_obv_divergence(
    close: pd.Series,
    obv: pd.Series,
    *,
    lookback: int = config.OBV_DIVERGENCE_LOOKBACK,
) -> dict[str, str | float]:
    """Detect divergence between price and OBV over the last lookback bars using least-squares slope."""
    if not isinstance(close, pd.Series) or not isinstance(obv, pd.Series):
        raise TypeError("close and obv must be pandas Series")
        
    L = min(len(close), lookback)
    if L < 2:
        return {
            "state": "neutral",
            "price_slope": 0.0,
            "obv_slope": 0.0,
        }
        
    x = np.arange(L, dtype=float)
    y_close = close.iloc[-L:].values
    y_obv = obv.iloc[-L:].values
    
    price_slope = float(np.polyfit(x, y_close, 1)[0])
    obv_slope = float(np.polyfit(x, y_obv, 1)[0])
    
    eps = 1e-9
    if abs(price_slope) < eps or abs(obv_slope) < eps:
        state = "neutral"
    elif price_slope < 0 and obv_slope > 0:
        state = "bullish_divergence"
    elif price_slope > 0 and obv_slope < 0:
        state = "bearish_divergence"
    elif (price_slope > 0 and obv_slope > 0) or (price_slope < 0 and obv_slope < 0):
        state = "confirming"
    else:
        state = "neutral"
        
    return {
        "state": state,
        "price_slope": price_slope,
        "obv_slope": obv_slope,
    }


def compute_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int | None = None,
) -> pd.Series:
    """Calculate Volume Weighted Average Price (VWAP) daily-bar approximation (anchored or rolling)."""
    if (not isinstance(high, pd.Series) or not isinstance(low, pd.Series) or
            not isinstance(close, pd.Series) or not isinstance(volume, pd.Series)):
        raise TypeError("high, low, close, and volume must be pandas Series")
        
    if not (high.index.equals(low.index) and low.index.equals(close.index) and close.index.equals(volume.index)):
        raise ValueError("All inputs must have matching indexes and lengths")
        
    tp = (high + low + close) / 3.0
    
    if period is None:
        cum_vol = volume.cumsum()
        vwap = (tp * volume).cumsum() / cum_vol
    else:
        roll_vol = volume.rolling(period, min_periods=period).sum()
        vwap = (tp * volume).rolling(period, min_periods=period).sum() / roll_vol
        
    return vwap.rename("VWAP")


def vwap_state(
    close: pd.Series | float,
    vwap: pd.Series | float,
) -> dict[str, str | float]:
    """Determine the state and percentage distance of close relative to the VWAP daily-bar approximation."""
    c_val = close.iloc[-1] if isinstance(close, pd.Series) else close
    v_val = vwap.iloc[-1] if isinstance(vwap, pd.Series) else vwap
    
    if pd.isna(c_val) or pd.isna(v_val) or v_val == 0 or np.isinf(c_val) or np.isinf(v_val):
        return {
            "state": "unknown",
            "distance_pct": float("nan"),
        }
        
    state = "above_vwap" if c_val > v_val else "below_vwap"
    distance_pct = float((c_val - v_val) / v_val * 100.0)
    
    return {
        "state": state,
        "distance_pct": distance_pct,
    }


def compute_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute Money Flow Index (MFI) 14."""
    if df.empty:
        raise ValueError("df cannot be empty")
        
    for col in ("High", "Low", "Close", "Volume"):
        if col not in df.columns:
            raise ValueError(f"df must contain '{col}' column")
            
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    volume = df["Volume"]
    
    tp = (high + low + close) / 3.0
    tp_diff = tp.diff()
    mf = tp * volume
    
    pmf = np.where(tp_diff > 0, mf, 0.0)
    nmf = np.where(tp_diff < 0, mf, 0.0)
    
    pmf_sum = pd.Series(pmf, index=df.index).rolling(window=period, min_periods=period).sum()
    nmf_sum = pd.Series(nmf, index=df.index).rolling(window=period, min_periods=period).sum()
    
    mr = pmf_sum / nmf_sum.replace(0.0, float("nan"))
    mfi = 100.0 - (100.0 / (1.0 + mr.fillna(0.0)))
    
    mfi = mfi.where(nmf_sum != 0.0, 100.0)
    mfi = mfi.where(~((pmf_sum == 0.0) & (nmf_sum == 0.0)), 50.0)
    mfi = mfi.where(pmf_sum.notna() & nmf_sum.notna(), np.nan)
    
    return mfi.rename("MFI")


def mfi_state(mfi_value: pd.Series | float) -> str:
    """Classify MFI state.
    
    - "overbought": >= 80
    - "oversold": <= 20
    - "neutral": any other value (or NaN)
    """
    val = mfi_value.iloc[-1] if isinstance(mfi_value, pd.Series) else mfi_value
    if pd.isna(val):
        return "neutral"
    if val >= config.MFI_OVERBOUGHT:
        return "overbought"
    elif val <= config.MFI_OVERSOLD:
        return "oversold"
    else:
        return "neutral"


def compute_avwap(df: pd.DataFrame, anchor_idx: int) -> pd.Series:
    """Compute Anchored VWAP from anchor_idx index."""
    if df.empty:
        raise ValueError("df cannot be empty")
        
    for col in ("High", "Low", "Close", "Volume"):
        if col not in df.columns:
            raise ValueError(f"df must contain '{col}' column")
            
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    volume = df["Volume"]
    
    tp = (high + low + close) / 3.0
    
    avwap = pd.Series(index=df.index, dtype=float)
    if anchor_idx < 0 or anchor_idx >= len(df):
        return avwap
        
    sub_tp = tp.iloc[anchor_idx:]
    sub_vol = volume.iloc[anchor_idx:]
    
    cum_pv = (sub_tp * sub_vol).cumsum()
    cum_v = sub_vol.cumsum()
    
    avwap.iloc[anchor_idx:] = cum_pv / cum_v.replace(0.0, float("nan"))
    return avwap.rename(f"AVWAP_{anchor_idx}")
