"""Seasonality indicators module.

Calculates calendar monthly return distributions and seasonality statistics.
"""
from __future__ import annotations

import pandas as pd


# A month is considered COMPLETE if its last observation falls within this
# many calendar days of the calendar month end. 3 covers a weekend plus one
# holiday at month end; longer closures (rare) err on the side of DROPPING a
# complete month (losing one sample) rather than keeping a partial one
# (adding a wrong sample).
PARTIAL_MONTH_TOLERANCE_DAYS = 3


def monthly_returns(close: pd.Series, *, drop_partial_last: bool = True) -> pd.Series:
    """Calculate month-end returns from a daily closing price series.

    By default the final month is DROPPED when the series ends mid-month:
    a month-to-date return (e.g. 3 trading days of July on a July-3rd run)
    is not a monthly return, and including it would silently bias the
    seasonality heatmap and the per-month mean/win-rate statistics.
    The first partial month needs no such guard: pct_change() already makes
    it NaN (it only serves as the base for the following month).
    """
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas.Series")
    if not isinstance(close.index, pd.DatetimeIndex):
        raise TypeError("close series must have a DatetimeIndex")

    monthly_closes = close.resample("ME").last()

    if drop_partial_last and len(monthly_closes) > 0:
        month_end = monthly_closes.index[-1]
        last_obs = close.index.max()
        if (month_end.date() - last_obs.date()).days > PARTIAL_MONTH_TOLERANCE_DAYS:
            monthly_closes = monthly_closes.iloc[:-1]

    return monthly_closes.pct_change()


def seasonality_table(monthly: pd.Series) -> pd.DataFrame:
    """Pivot monthly returns into a table indexed by year, with columns 1..12."""
    if not isinstance(monthly, pd.Series):
        raise TypeError("monthly must be a pandas.Series")
    if not isinstance(monthly.index, pd.DatetimeIndex):
        raise TypeError("monthly series must have a DatetimeIndex")
        
    df = pd.DataFrame({
        "return": monthly,
        "year": monthly.index.year,
        "month": monthly.index.month,
    })
    
    pivoted = df.pivot(index="year", columns="month", values="return")
    return pivoted.reindex(columns=list(range(1, 13)))


def monthly_summary(monthly: pd.Series) -> pd.DataFrame:
    """Calculate mean return and win rate for each calendar month 1..12.
    
    Returns:
        pd.DataFrame: Columns "mean" and "win_rate", indexed by month 1..12.
    """
    if not isinstance(monthly, pd.Series):
        raise TypeError("monthly must be a pandas.Series")
    if not isinstance(monthly.index, pd.DatetimeIndex):
        raise TypeError("monthly series must have a DatetimeIndex")
        
    df = pd.DataFrame({
        "return": monthly,
        "month": monthly.index.month,
    }).dropna()
    
    if df.empty:
        return pd.DataFrame(
            {"mean": [float("nan")] * 12, "win_rate": [float("nan")] * 12},
            index=list(range(1, 13))
        )
        
    summary = df.groupby("month")["return"].agg(
        mean="mean",
        win_rate=lambda x: float((x > 0.0).mean())
    )
    return summary.reindex(list(range(1, 13)))
