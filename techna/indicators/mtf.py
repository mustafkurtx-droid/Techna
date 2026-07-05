"""Multiple Timeframe Context: Weekly timeframe analysis and trend alignment."""
from __future__ import annotations

import pandas as pd

from techna import config
from techna.indicators import (
    compute_sma,
    trend_state,
    compute_rsi,
    rsi_state,
    compute_macd,
    macd_state,
    compute_adx,
    trend_regime,
)


def resample_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily price DataFrame to weekly (Friday-ending W-FRI).
    
    Drops the final weekly bar if it is considered partial/incomplete
    according to: last_daily_date < weekly_index[-1] - 2 days.
    
    Also drops empty weeks where Close is missing.
    """
    if df.empty:
        return pd.DataFrame()
        
    weekly_df = df.resample("W-FRI").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    })
    
    # Drop partial final week if bourses ended on Mon/Tue (e.g. daily index is behind Friday label by > 2 days)
    last_daily_date = df.index[-1]
    last_weekly_label = weekly_df.index[-1]
    if last_daily_date < last_weekly_label - pd.Timedelta(days=2):
        weekly_df = weekly_df.iloc[:-1]
        
    return weekly_df.dropna(subset=["Close"])


def compute_weekly_context(df: pd.DataFrame, daily_trend: str) -> dict:
    """Compute weekly timeframe indicators and align with daily trend.
    
    Returns:
        dict: A dictionary containing weekly context metrics and status.
    """
    weekly_df = resample_to_weekly(df)
    
    if len(weekly_df) < config.WEEKLY_SMA_SLOW:
        return {
            "status": "warning",
            "weekly_bars": len(weekly_df),
            "weekly_trend_state": "sideways",
            "weekly_rsi": float("nan"),
            "weekly_rsi_state": "neutral",
            "weekly_macd_state": "bearish",
            "weekly_adx": float("nan"),
            "weekly_trend_regime": "ranging",
            "alignment": "mixed",
            "warning": (
                f"Insufficient history ({len(weekly_df)} weekly bars) for weekly "
                f"SMA{config.WEEKLY_SMA_SLOW} (needs >={config.WEEKLY_SMA_SLOW})."
            ),
        }

    close = weekly_df["Close"]

    # Calculate indicators
    weekly_sma10 = compute_sma(close, config.WEEKLY_SMA_FAST)
    weekly_sma40 = compute_sma(close, config.WEEKLY_SMA_SLOW)

    weekly_trend = trend_state(close, weekly_sma10, weekly_sma40)

    weekly_rsi_series = compute_rsi(close, config.RSI_PERIOD)
    weekly_rsi_val = weekly_rsi_series.iloc[-1]
    weekly_rsi_state_val = rsi_state(weekly_rsi_val)
    
    weekly_macd_df = compute_macd(close, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL)
    weekly_macd_state_val = macd_state(weekly_macd_df["hist"])
    
    weekly_adx_df = compute_adx(weekly_df, config.ADX_PERIOD)
    weekly_adx_val = weekly_adx_df["adx"].iloc[-1]
    weekly_adx_regime_val = trend_regime(
        weekly_adx_df["adx"],
        weekly_adx_df["plus_di"],
        weekly_adx_df["minus_di"],
    )
    
    # Alignment calculation
    if daily_trend == "uptrend" and weekly_trend == "uptrend":
        alignment_val = "aligned_bullish"
    elif daily_trend == "downtrend" and weekly_trend == "downtrend":
        alignment_val = "aligned_bearish"
    else:
        alignment_val = "mixed"
        
    return {
        "status": "ok",
        "weekly_bars": len(weekly_df),
        "weekly_trend_state": weekly_trend,
        "weekly_rsi": float(weekly_rsi_val),
        "weekly_rsi_state": weekly_rsi_state_val,
        "weekly_macd_state": weekly_macd_state_val,
        "weekly_adx": float(weekly_adx_val),
        "weekly_trend_regime": weekly_adx_regime_val,
        "alignment": alignment_val,
        # Keep raw series for plotting
        "_weekly_df": weekly_df,
        "_sma10": weekly_sma10,
        "_sma40": weekly_sma40,
        "_rsi": weekly_rsi_series,
    }
