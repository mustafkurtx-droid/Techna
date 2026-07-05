"""Relative Strength indicators module.

Compares asset performance against a benchmark index.
"""
from __future__ import annotations

import pandas as pd


def align_close(
    asset: pd.Series,
    benchmark: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Align asset and benchmark series on common dates using inner join."""
    if not isinstance(asset, pd.Series):
        raise TypeError("asset must be a pandas.Series")
    if not isinstance(benchmark, pd.Series):
        raise TypeError("benchmark must be a pandas.Series")
        
    asset_aligned = asset.copy()
    bench_aligned = benchmark.copy()
    
    if asset_aligned.index.tz is not None:
        asset_aligned.index = asset_aligned.index.tz_convert("UTC").tz_localize(None)
    if bench_aligned.index.tz is not None:
        bench_aligned.index = bench_aligned.index.tz_convert("UTC").tz_localize(None)
        
    df = pd.DataFrame({"asset": asset_aligned, "bench": bench_aligned}).dropna()
    return df["asset"], df["bench"]


def relative_strength(
    asset_close: pd.Series,
    benchmark_close: pd.Series,
) -> pd.Series:
    """Calculate the relative strength ratio of asset to benchmark."""
    if not isinstance(asset_close, pd.Series):
        raise TypeError("asset_close must be a pandas.Series")
    if not isinstance(benchmark_close, pd.Series):
        raise TypeError("benchmark_close must be a pandas.Series")
        
    return asset_close / benchmark_close


def rebased_performance(close: pd.Series) -> pd.Series:
    """Rebase the close series so that it starts at exactly 100.0."""
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas.Series")
    if len(close) == 0:
        return pd.Series(dtype=float)
        
    return (close / close.iloc[0]) * 100.0


def rs_state(rs: pd.Series, ma: pd.Series) -> str:
    """Determine the relative strength state of the asset.
    
    Returns:
        "outperforming" if RS > RS_MA and RS is increasing.
        "underperforming" if RS < RS_MA and RS is decreasing.
        "neutral" otherwise.
    """
    if not isinstance(rs, pd.Series):
        raise TypeError("rs must be a pandas.Series")
    if not isinstance(ma, pd.Series):
        raise TypeError("ma must be a pandas.Series")
        
    if len(rs) < 2 or pd.isna(rs.iloc[-1]) or pd.isna(rs.iloc[-2]) or pd.isna(ma.iloc[-1]):
        return "neutral"
        
    last_rs = float(rs.iloc[-1])
    prev_rs = float(rs.iloc[-2])
    last_ma = float(ma.iloc[-1])
    
    if last_rs > last_ma and last_rs > prev_rs:
        return "outperforming"
    elif last_rs < last_ma and last_rs < prev_rs:
        return "underperforming"
    return "neutral"
