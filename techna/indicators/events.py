"""Today's Events Detector: Scans final bar for crossovers, boundary breaches, and regime shifts."""
from __future__ import annotations

import pandas as pd

from techna import config


def _ev_rsi_zone(context: dict) -> list[dict]:
    """Check if RSI crossed 70 or 30 zones on the final bar."""
    rsi = context.get("rsi")
    if rsi is None or len(rsi) < 2:
        return []
    
    prev_rsi = rsi.iloc[-2]
    curr_rsi = rsi.iloc[-1]
    
    if pd.isna(prev_rsi) or pd.isna(curr_rsi):
        return []
        
    ob, os_ = config.RSI_OVERBOUGHT, config.RSI_OVERSOLD
    events = []
    # Overbought entry/exit
    if prev_rsi < ob and curr_rsi >= ob:
        events.append({
            "type": "rsi_zone_entry",
            "direction": "bullish",
            "detail": f"RSI entered the overbought zone (>={ob:.0f}) at {curr_rsi:.2f}."
        })
    elif prev_rsi >= ob and curr_rsi < ob:
        events.append({
            "type": "rsi_zone_exit",
            "direction": "bearish",
            "detail": f"RSI exited the overbought zone at {curr_rsi:.2f}."
        })

    # Oversold entry/exit
    if prev_rsi > os_ and curr_rsi <= os_:
        events.append({
            "type": "rsi_zone_entry",
            "direction": "bearish",
            "detail": f"RSI entered the oversold zone (<={os_:.0f}) at {curr_rsi:.2f}."
        })
    elif prev_rsi <= os_ and curr_rsi > os_:
        events.append({
            "type": "rsi_zone_exit",
            "direction": "bullish",
            "detail": f"RSI exited the oversold zone at {curr_rsi:.2f}."
        })

    return events


def _ev_macd_hist_flip(context: dict) -> list[dict]:
    """Check if MACD histogram crossed above or below the zero line on the last bar."""
    macd = context.get("macd")
    if macd is None or len(macd) < 2 or "hist" not in macd.columns:
        return []
        
    hist = macd["hist"]
    prev_h = hist.iloc[-2]
    curr_h = hist.iloc[-1]
    
    if pd.isna(prev_h) or pd.isna(curr_h):
        return []
        
    if prev_h <= 0.0 and curr_h > 0.0:
        return [{
            "type": "macd_hist_flip",
            "direction": "bullish",
            "detail": f"MACD histogram crossed above zero line to {curr_h:.4f}."
        }]
    elif prev_h >= 0.0 and curr_h < 0.0:
        return [{
            "type": "macd_hist_flip",
            "direction": "bearish",
            "detail": f"MACD histogram crossed below zero line to {curr_h:.4f}."
        }]
        
    return []


def _ev_ma_cross_today(context: dict) -> list[dict]:
    """Check if SMA50 crossed SMA200 (Golden/Death Cross) on the last bar."""
    cross_df = context.get("cross_df")
    if cross_df is None or cross_df.empty or "cross" not in cross_df.columns:
        return []
        
    last_cross = cross_df["cross"].iloc[-1]
    if last_cross == "golden":
        return [{
            "type": "ma_cross_today",
            "direction": "bullish",
            "detail": "SMA50 crossed above SMA200 (Golden Cross)."
        }]
    elif last_cross == "death":
        return [{
            "type": "ma_cross_today",
            "direction": "bearish",
            "detail": "SMA50 crossed below SMA200 (Death Cross)."
        }]
        
    return []


def _ev_bollinger_cross(context: dict) -> list[dict]:
    """Check if price crossed above/below or re-entered the Bollinger Bands on the last bar."""
    df = context.get("df")
    boll = context.get("bollinger")
    if df is None or len(df) < 2 or boll is None or len(boll) < 2:
        return []
        
    close = df["Close"]
    upper = boll["upper"]
    lower = boll["lower"]
    
    prev_c, curr_c = close.iloc[-2], close.iloc[-1]
    prev_u, curr_u = upper.iloc[-2], upper.iloc[-1]
    prev_l, curr_l = lower.iloc[-2], lower.iloc[-1]
    
    if any(pd.isna(x) for x in (prev_c, curr_c, prev_u, curr_u, prev_l, curr_l)):
        return []
        
    events = []
    # Upper band cross/re-entry
    if prev_c <= prev_u and curr_c > curr_u:
        events.append({
            "type": "bollinger_cross",
            "direction": "bullish",
            "detail": "Price crossed above the upper Bollinger Band."
        })
    elif prev_c > prev_u and curr_c <= curr_u:
        events.append({
            "type": "bollinger_cross",
            "direction": "bearish",
            "detail": "Price crossed back below the upper Bollinger Band."
        })
        
    # Lower band cross/re-entry
    if prev_c >= prev_l and curr_c < curr_l:
        events.append({
            "type": "bollinger_cross",
            "direction": "bearish",
            "detail": "Price crossed below the lower Bollinger Band."
        })
    elif prev_c < prev_l and curr_c >= curr_l:
        events.append({
            "type": "bollinger_cross",
            "direction": "bullish",
            "detail": "Price crossed back above the lower Bollinger Band."
        })
        
    return events


def _ev_range_52w_break(context: dict) -> list[dict]:
    """Check if price broke out of the previous 52-week High/Low (excluding today's bar)."""
    df = context.get("df")
    window = config.WEEK52_WINDOW
    if df is None or len(df) < window + 1:  # needs `window` bars + 1 for today
        return []

    high = df["High"]
    low = df["Low"]

    # Pre-calculate rolling high/low of yesterday (look-ahead guard: shift 1).
    # Same window as compute_52week_range() -- if config.WEEK52_WINDOW changes,
    # this event detector must track it, not silently keep the old window.
    prev_highs = high.shift(1).rolling(window=window, min_periods=window).max()
    prev_lows = low.shift(1).rolling(window=window, min_periods=window).min()
    
    prev_high = prev_highs.iloc[-1]
    prev_low = prev_lows.iloc[-1]
    
    if pd.isna(prev_high) or pd.isna(prev_low):
        return []
        
    events = []
    if high.iloc[-1] > prev_high:
        events.append({
            "type": "range_52w_break",
            "direction": "bullish",
            "detail": f"Price broke out above the 52-week high of {prev_high:.2f}."
        })
    elif low.iloc[-1] < prev_low:
        events.append({
            "type": "range_52w_break",
            "direction": "bearish",
            "detail": f"Price broke out below the 52-week low of {prev_low:.2f}."
        })
        
    return events


def _ev_vwap_cross(context: dict) -> list[dict]:
    """Check if price crossed above or below the daily VWAP on the final bar."""
    df = context.get("df")
    vwap = context.get("vwap")
    if df is None or len(df) < 2 or vwap is None or len(vwap) < 2:
        return []
        
    close = df["Close"]
    prev_c, curr_c = close.iloc[-2], close.iloc[-1]
    prev_v, curr_v = vwap.iloc[-2], vwap.iloc[-1]
    
    if any(pd.isna(x) for x in (prev_c, curr_c, prev_v, curr_v)):
        return []
        
    if prev_c <= prev_v and curr_c > curr_v:
        return [{
            "type": "vwap_cross",
            "direction": "bullish",
            "detail": "Price crossed above the daily VWAP."
        }]
    elif prev_c >= prev_v and curr_c < curr_v:
        return [{
            "type": "vwap_cross",
            "direction": "bearish",
            "detail": "Price crossed below the daily VWAP."
        }]
        
    return []


def _ev_structural_break_recent(context: dict) -> list[dict]:
    """Check if any structural break detected occurred in the last 5 bars of the series."""
    df = context.get("df")
    econ = context.get("econometrics")
    if df is None or econ is None or "breaks" not in econ:
        return []
        
    breaks = econ["breaks"]
    N = len(df)
    
    events = []
    for b in breaks:
        idx = b.get("index")
        if idx is not None and (N - 1 - idx) < 5:
            b_type = b.get("type", "unknown")
            b_date = b.get("date", "N/A")
            events.append({
                "type": "structural_break_recent",
                "direction": "neutral",
                "detail": f"A structural break of type {b_type} was detected on {b_date}."
            })
            
    return events


def _ev_squeeze(context: dict) -> list[dict]:
    """Check if squeeze started or released on the last bar."""
    sq = context.get("squeeze")
    if sq is None or "_squeeze_active_series" not in sq:
        return []
        
    active_series = sq["_squeeze_active_series"]
    if len(active_series) < 2:
        return []
        
    prev_active = bool(active_series.iloc[-2])
    curr_active = bool(active_series.iloc[-1])
    
    events = []
    if not prev_active and curr_active:
        events.append({
            "type": "squeeze_start",
            "direction": "neutral",
            "detail": "Bollinger Squeeze activated (duration: 1 bar) indicating potential volatility contraction."
        })
    elif prev_active and not curr_active:
        events.append({
            "type": "squeeze_release",
            "direction": "neutral",
            "detail": "Bollinger Squeeze released. Price is breaking out of the compression zone."
        })
        
    return events


def _ev_stoch_zone(context: dict) -> list[dict]:
    """Check if Stochastic Slow %K entered overbought or oversold zone on the last bar."""
    stoch = context.get("stochastic")
    if stoch is None or "_slow_k_series" not in stoch:
        return []
        
    k_series = stoch["_slow_k_series"]
    if len(k_series) < 2:
        return []
        
    prev_k = k_series.iloc[-2]
    curr_k = k_series.iloc[-1]
    
    if pd.isna(prev_k) or pd.isna(curr_k):
        return []
        
    ob, os_ = config.STOCH_OVERBOUGHT, config.STOCH_OVERSOLD
    events = []
    # Enter overbought (crosses the threshold from below)
    if prev_k < ob and curr_k >= ob:
        events.append({
            "type": "stoch_zone_entry",
            "direction": "neutral",
            "detail": f"Stochastic Slow %K entered overbought zone at {curr_k:.2f}."
        })
    # Enter oversold (crosses the threshold from above)
    elif prev_k > os_ and curr_k <= os_:
        events.append({
            "type": "stoch_zone_entry",
            "direction": "neutral",
            "detail": f"Stochastic Slow %K entered oversold zone at {curr_k:.2f}."
        })

    return events


def _ev_donchian_breakout(context: dict) -> list[dict]:
    """Check for Donchian Channel (20 & 55 day) breakouts on the last bar.
    
    A breakout occurs when the Close price crosses beyond the previous day's band.
    """
    donchian = context.get("donchian")
    if donchian is None or "_df" not in donchian:
        return []
        
    df_d = donchian["_df"]
    if len(df_d) < 2:
        return []
        
    close_series = donchian.get("_close_series")
    if close_series is None or len(close_series) < 2:
        return []
        
    curr_close = close_series.iloc[-1]

    events = []
    for period in (20, 55):
        upper_col = f"upper_{period}"
        lower_col = f"lower_{period}"

        if upper_col not in df_d.columns or lower_col not in df_d.columns:
            continue

        # The channel series already exclude the current bar (shift(1) inside
        # compute_donchian), so the LAST value is the prior n-day extreme.
        prev_upper = df_d[upper_col].iloc[-1]
        prev_lower = df_d[lower_col].iloc[-1]
        
        if pd.isna(prev_upper) or pd.isna(prev_lower) or pd.isna(curr_close):
            continue
            
        if curr_close > prev_upper:
            events.append({
                "type": "donchian_breakout",
                "direction": "bullish",
                "detail": f"Price broke out above the Donchian Upper {period}-day band at {curr_close:.2f}."
            })
        elif curr_close < prev_lower:
            events.append({
                "type": "donchian_breakout",
                "direction": "bearish",
                "detail": f"Price broke out below the Donchian Lower {period}-day band at {curr_close:.2f}."
            })
            
    return events


def _ev_mfi_zone(context: dict) -> list[dict]:
    """Check if MFI(14) entered overbought or oversold zone on the last bar."""
    volume_ctx = context.get("volume")
    if volume_ctx is None or "_mfi_series" not in volume_ctx:
        return []
        
    mfi_series = volume_ctx["_mfi_series"]
    if len(mfi_series) < 2:
        return []
        
    prev_mfi = mfi_series.iloc[-2]
    curr_mfi = mfi_series.iloc[-1]
    
    if pd.isna(prev_mfi) or pd.isna(curr_mfi):
        return []
        
    ob, os_ = config.MFI_OVERBOUGHT, config.MFI_OVERSOLD
    events = []
    # Enter overbought (crosses the threshold from below)
    if prev_mfi < ob and curr_mfi >= ob:
        events.append({
            "type": "mfi_zone_entry",
            "direction": "neutral",
            "detail": f"MFI(14) entered overbought zone at {curr_mfi:.2f}."
        })
    # Enter oversold (crosses the threshold from above)
    elif prev_mfi > os_ and curr_mfi <= os_:
        events.append({
            "type": "mfi_zone_entry",
            "direction": "neutral",
            "detail": f"MFI(14) entered oversold zone at {curr_mfi:.2f}."
        })

    return events


def _ev_candle_patterns(context: dict) -> list[dict]:
    """Check if any candlestick pattern was detected on the final bar."""
    candles = context.get("candles")
    if candles is None or "patterns" not in candles:
        return []
        
    patterns = candles["patterns"]
    
    events = []
    dirs = {
        "doji": "neutral",
        "hammer": "bullish",
        "shooting_star": "bearish",
        "bullish_engulfing": "bullish",
        "bearish_engulfing": "bearish",
    }
    
    details = {
        "doji": "Doji pattern detected: indicating market indecision.",
        "hammer": "Hammer pattern detected: indicating potential bullish reversal.",
        "shooting_star": "Shooting Star pattern detected: indicating potential bearish reversal.",
        "bullish_engulfing": "Bullish Engulfing pattern detected: indicating potential bullish reversal.",
        "bearish_engulfing": "Bearish Engulfing pattern detected: indicating potential bearish reversal.",
    }
    
    for pat_name, series in patterns.items():
        if len(series) > 0 and bool(series.iloc[-1]):
            events.append({
                "type": "candle_pattern_detected",
                "direction": dirs[pat_name],
                "detail": details[pat_name]
            })
            
    return events


EVENT_DETECTORS = [
    _ev_rsi_zone,
    _ev_macd_hist_flip,
    _ev_ma_cross_today,
    _ev_bollinger_cross,
    _ev_range_52w_break,
    _ev_vwap_cross,
    _ev_structural_break_recent,
    _ev_squeeze,
    _ev_stoch_zone,
    _ev_donchian_breakout,
    _ev_mfi_zone,
    _ev_candle_patterns,
]


def compute_events(context: dict) -> list[dict]:
    """Run all event detectors and return aggregated events list."""
    from techna.report_builder import assert_no_advice
    all_events = []
    for detector in EVENT_DETECTORS:
        detected = detector(context)
        for ev in detected:
            assert_no_advice(ev["detail"])
            all_events.append(ev)
    return all_events
