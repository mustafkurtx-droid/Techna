"""Empirical base rates indicators module.

Evaluates historical return statistics conditioned on technical events.
"""
from __future__ import annotations

import pandas as pd


def forward_return(close: pd.Series, horizon: int) -> pd.Series:
    """Calculate the historical forward return over a given horizon.
    
    WARNING: This function accesses future data (lookahead) by shifting prices
    backwards: close[t + horizon] / close[t] - 1. It is strictly for historical
    descriptive statistics and conditional return distribution analysis, and must
    never be used for live signal generation.
    """
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas.Series")
    if horizon <= 0:
        raise ValueError("horizon must be a positive integer")
        
    return close.shift(-horizon) / close - 1.0


def conditional_stats(
    condition: pd.Series,
    fwd: pd.Series,
    *,
    min_sample: int,
) -> dict:
    """Calculate statistics of forward returns where the condition is True.
    
    Returns:
        dict: Containing keys: "n", "mean", "median", "win_rate", "p25", "p75",
            "std", "reliable".
    """
    if not isinstance(condition, pd.Series):
        raise TypeError("condition must be a pandas.Series")
    if not isinstance(fwd, pd.Series):
        raise TypeError("fwd must be a pandas.Series")
        
    # Align and drop NaNs
    df = pd.DataFrame({"cond": condition, "fwd": fwd}).dropna()
    cond_fwd = df.loc[df["cond"], "fwd"]
    
    n = len(cond_fwd)
    if n == 0:
        return {
            "n": 0,
            "mean": float("nan"),
            "median": float("nan"),
            "win_rate": float("nan"),
            "p25": float("nan"),
            "p75": float("nan"),
            "std": float("nan"),
            "reliable": False,
        }
        
    win_rate = float((cond_fwd > 0.0).mean())
    mean_val = float(cond_fwd.mean())
    median_val = float(cond_fwd.median())
    p25 = float(cond_fwd.quantile(0.25))
    p75 = float(cond_fwd.quantile(0.75))
    std_val = float(cond_fwd.std()) if n > 1 else 0.0
    
    return {
        "n": n,
        "mean": mean_val,
        "median": median_val,
        "win_rate": win_rate,
        "p25": p25,
        "p75": p75,
        "std": std_val,
        "reliable": n >= min_sample,
    }


def baseline_stats(fwd: pd.Series) -> dict:
    """Calculate baseline statistics of forward returns across all days."""
    if not isinstance(fwd, pd.Series):
        raise TypeError("fwd must be a pandas.Series")
        
    all_true = pd.Series(True, index=fwd.index)
    return conditional_stats(all_true, fwd, min_sample=1)
