"""Risk context indicators module.

Provides 52-week position calculations, drawdown episodes detection,
liquidity metrics, and systematic beta analysis.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from techna import config


def compute_52week_range(close: pd.Series, *, window: int = config.WEEK52_WINDOW) -> dict:
    """Calculate the 52-week position and range details."""
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas.Series")
        
    w = min(window, len(close))
    if w == 0:
        return {
            "high": float("nan"),
            "low": float("nan"),
            "current": float("nan"),
            "position_pct": float("nan"),
            "state": "mid_range",
            "window_used": 0,
        }
        
    recent = close.iloc[-w:]
    high = float(recent.max())
    low = float(recent.min())
    current = float(close.iloc[-1])
    rng = high - low
    
    if rng == 0:
        position_pct = float("nan")
    else:
        position_pct = float((current - low) / rng * 100.0)
        
    if pd.isna(position_pct):
        state = "mid_range"
    elif position_pct >= config.WEEK52_HIGH_PCT:
        state = "near_52w_high"
    elif position_pct <= config.WEEK52_LOW_PCT:
        state = "near_52w_low"
    else:
        state = "mid_range"
        
    return {
        "high": high,
        "low": low,
        "current": current,
        "position_pct": position_pct,
        "state": state,
        "window_used": w,
    }


def compute_drawdown_series(close: pd.Series) -> pd.DataFrame:
    """Calculate the running maximum and drawdown series."""
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas.Series")
        
    if len(close) == 0:
        return pd.DataFrame(columns=["close", "running_max", "drawdown"])
        
    running_max = close.cummax()
    drawdown = (close - running_max) / running_max
    
    return pd.DataFrame({
        "close": close,
        "running_max": running_max,
        "drawdown": drawdown,
    }, index=close.index)


def find_drawdown_episodes(close: pd.Series, top_n: int = 3) -> list[dict]:
    """Identify historical drawdown episodes sorted by peak-to-trough severity."""
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas.Series")
        
    if len(close) == 0:
        return []
        
    df_dd = compute_drawdown_series(close)
    dd_arr = df_dd["drawdown"].values
    dates = close.index
    
    episodes = []
    in_episode = False
    peak_date = None
    trough_date = None
    trough_pct = 0.0
    
    i = 0
    n_len = len(close)
    while i < n_len:
        if not in_episode:
            if dd_arr[i] < 0:
                in_episode = True
                # Search backward for the peak before drawdown started
                peak_date = dates[0]
                for j in range(i, -1, -1):
                    if dd_arr[j] == 0:
                        peak_date = dates[j]
                        break
                trough_date = dates[i]
                trough_pct = dd_arr[i]
            i += 1
        else:
            if dd_arr[i] == 0:
                # Recovered!
                recovery_date = dates[i]
                assert trough_date is not None
                days = (recovery_date - trough_date).days
                assert peak_date is not None
                episodes.append({
                    "peak_date": peak_date.strftime("%Y-%m-%d") if hasattr(peak_date, "strftime") else str(peak_date),
                    "trough_date": trough_date.strftime("%Y-%m-%d") if hasattr(trough_date, "strftime") else str(trough_date),
                    "trough_pct": float(trough_pct),
                    "recovery_date": recovery_date.strftime("%Y-%m-%d") if hasattr(recovery_date, "strftime") else str(recovery_date),
                    "days_to_recover": int(days),
                })
                in_episode = False
            else:
                # Update trough if deeper
                if dd_arr[i] < trough_pct:
                    trough_pct = dd_arr[i]
                    trough_date = dates[i]
            i += 1
            
    if in_episode:
        assert peak_date is not None
        assert trough_date is not None
        episodes.append({
            "peak_date": peak_date.strftime("%Y-%m-%d") if hasattr(peak_date, "strftime") else str(peak_date),
            "trough_date": trough_date.strftime("%Y-%m-%d") if hasattr(trough_date, "strftime") else str(trough_date),
            "trough_pct": float(trough_pct),
            "recovery_date": None,
            "days_to_recover": None,
        })
        
    episodes.sort(key=lambda x: x["trough_pct"])
    return episodes[:top_n]


def compute_liquidity_metrics(volume: pd.Series, close: pd.Series) -> dict:
    """Calculate liquidity traded values and classify the liquidity regime."""
    if not isinstance(volume, pd.Series) or not isinstance(close, pd.Series):
        raise TypeError("volume and close must be pandas.Series")
        
    if len(volume) == 0 or len(close) == 0:
        return {
            "adv20": 0.0,
            "adv90": 0.0,
            "avg_value_20": 0.0,
            "state": "low_liquidity",
            "thresholds": {"high": config.LIQ_HIGH_VALUE, "low": config.LIQ_LOW_VALUE},
        }
        
    adv20 = float(volume.tail(20).mean())
    adv90 = float(volume.tail(90).mean())
    
    dollar_vol = volume * close
    addv20 = float(dollar_vol.tail(20).mean())
    
    if addv20 >= config.LIQ_HIGH_VALUE:
        state = "high_liquidity"
    elif addv20 >= config.LIQ_LOW_VALUE:
        state = "moderate_liquidity"
    else:
        state = "low_liquidity"
        
    return {
        "adv20": adv20,
        "adv90": adv90,
        "avg_value_20": addv20,
        "state": state,
        "thresholds": {"high": config.LIQ_HIGH_VALUE, "low": config.LIQ_LOW_VALUE},
    }


def compute_beta(stock_returns: pd.Series, benchmark_returns: pd.Series) -> dict:
    """Calculate systematic risk metrics (Beta, Alpha, R-Squared) against benchmark returns."""
    if not isinstance(stock_returns, pd.Series) or not isinstance(benchmark_returns, pd.Series):
        raise TypeError("inputs must be pandas.Series")
        
    aligned = pd.concat([stock_returns, benchmark_returns], axis=1, join="inner").dropna()
    if len(aligned) < 2:
        return {
            "beta": float("nan"),
            "alpha_annualized": float("nan"),
            "r_squared": float("nan"),
            "state": "low_beta",
            "n": len(aligned),
        }
        
    s_ret = aligned.iloc[:, 0].values
    b_ret = aligned.iloc[:, 1].values
    
    s_mean = np.mean(s_ret)
    b_mean = np.mean(b_ret)
    
    cov_val = np.sum((s_ret - s_mean) * (b_ret - b_mean))
    var_val = np.sum((b_ret - b_mean) ** 2)
    
    if var_val == 0:
        beta = float("nan")
    else:
        beta = float(cov_val / var_val)
        
    if pd.isna(beta):
        alpha_annualized = float("nan")
        r_squared = float("nan")
    else:
        alpha_daily = s_mean - beta * b_mean
        alpha_annualized = float(alpha_daily * 252.0)
        
        num_corr = np.sum((s_ret - s_mean) * (b_ret - b_mean))
        den_corr = np.sqrt(np.sum((s_ret - s_mean) ** 2) * np.sum((b_ret - b_mean) ** 2))
        
        if den_corr == 0:
            r_squared = float("nan")
        else:
            r_squared = float((num_corr / den_corr) ** 2)
            
    if pd.isna(beta):
        state = "low_beta"
    elif beta > config.BETA_HIGH:
        state = "high_beta"
    elif beta >= config.BETA_LOW:
        state = "market_beta"
    else:
        state = "low_beta"
        
    return {
        "beta": beta,
        "alpha_annualized": alpha_annualized,
        "r_squared": r_squared,
        "state": state,
        "n": len(aligned),
    }
