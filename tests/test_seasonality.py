"""Offline tests for Seasonality Return Heatmap (validates seasonality.feature)."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.seasonality import monthly_returns, monthly_summary, seasonality_table


def test_monthly_returns():
    """Scenario: Monthly returns use month-end closes; a partial final month
    (data ending mid-March here) is DROPPED, not reported as a monthly return."""
    # Create daily dates spanning 3 months, ending mid-March
    dates = pd.date_range("2024-01-15", "2024-03-15", freq="D")
    prices = pd.Series(dtype=float, index=dates)

    # Set prices so:
    # Jan 31: 100.0
    # Feb 29: 105.0 (Jan to Feb return: 105/100 - 1 = 5%)
    # Mar 15: 99.75 -- only half of March exists, so March must be excluded
    prices.loc["2024-01-31"] = 100.0
    prices.loc["2024-02-29"] = 105.0
    prices.loc["2024-03-15"] = 99.75
    # Fill remaining values with dummy prices to avoid NaNs
    prices = prices.ffill().bfill()

    ret = monthly_returns(prices)

    # Closes resampled: 2024-01-31: 100.0, 2024-02-29: 105.0.
    # March (data ends 15th, >3 calendar days before month end) is dropped:
    # a 2-week month-to-date move is not a monthly return.
    assert len(ret) == 2
    assert pd.isna(ret.iloc[0])  # first month return is NaN
    assert ret.iloc[1] == pytest.approx(0.05)


def test_monthly_returns_partial_last_month_kept_when_opted_in():
    """Scenario: drop_partial_last=False preserves the old include-everything
    behaviour for callers that explicitly want month-to-date."""
    dates = pd.date_range("2024-01-15", "2024-03-15", freq="D")
    prices = pd.Series(100.0, index=dates)
    prices.loc["2024-01-31"] = 100.0
    prices.loc["2024-02-29"] = 105.0
    prices.loc["2024-03-15"] = 99.75
    prices = prices.ffill().bfill()

    ret = monthly_returns(prices, drop_partial_last=False)
    assert len(ret) == 3
    assert ret.iloc[2] == pytest.approx(99.75 / 105.0 - 1.0)


def test_monthly_returns_weekend_month_end_counts_as_complete():
    """Scenario: a month whose last trading day is up to 3 calendar days
    before the calendar month end (weekend/holiday close) still counts as
    complete. 2024-03-31 was a Sunday; business days end Friday 2024-03-29,
    but we cut the data at Thursday 2024-03-28 to exercise the full 3-day
    tolerance -- March must be KEPT."""
    dates = pd.date_range("2024-01-01", "2024-03-28", freq="B")
    prices = pd.Series(100.0, index=dates)
    prices.loc["2024-01-31"] = 100.0
    prices.loc["2024-02-29"] = 105.0
    prices.loc["2024-03-28"] = 110.25

    ret = monthly_returns(prices)
    assert len(ret) == 3  # March kept: gap (Mar 31 - Mar 28) = 3 days <= tolerance
    assert ret.iloc[2] == pytest.approx(110.25 / 105.0 - 1.0)


def test_seasonality_table_and_summary():
    """Scenario: Seasonality table indexing/columns and summary calculations."""
    # Create a monthly series of returns
    dates = pd.to_datetime([
        "2023-11-30", "2023-12-31",
        "2024-01-31", "2024-02-29", "2024-11-30", "2024-12-31"
    ])
    returns = pd.Series([0.02, -0.01, 0.05, 0.03, -0.02, 0.01], index=dates)
    
    table = seasonality_table(returns)
    
    # Table should be indexed by years: 2023, 2024
    assert list(table.index) == [2023, 2024]
    # Columns are 1..12
    assert list(table.columns) == list(range(1, 13))
    
    # Verify cell values
    assert table.loc[2023, 11] == 0.02
    assert table.loc[2023, 12] == -0.01
    assert pd.isna(table.loc[2023, 1])
    assert table.loc[2024, 1] == 0.05
    assert table.loc[2024, 2] == 0.03
    assert table.loc[2024, 11] == -0.02
    assert table.loc[2024, 12] == 0.01
    
    # Verify monthly summary
    summary = monthly_summary(returns)
    
    # Summary columns should be "mean" and "win_rate"
    assert list(summary.columns) == ["mean", "win_rate"]
    assert list(summary.index) == list(range(1, 13))
    
    # Month 11: 2023-11 (0.02) and 2024-11 (-0.02)
    # Mean: 0.0, Win rate: 0.5
    assert summary.loc[11, "mean"] == pytest.approx(0.0)
    assert summary.loc[11, "win_rate"] == 0.5
    
    # Month 12: 2023-12 (-0.01) and 2024-12 (0.01)
    # Mean: 0.0, Win rate: 0.5
    assert summary.loc[12, "mean"] == pytest.approx(0.0)
    assert summary.loc[12, "win_rate"] == 0.5
    
    # Month 1: 2024-01 (0.05)
    # Mean: 0.05, Win rate: 1.0
    assert summary.loc[1, "mean"] == pytest.approx(0.05)
    assert summary.loc[1, "win_rate"] == 1.0
