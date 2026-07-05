"""Boundary conditions: every indicator must degrade gracefully at its limits.

These lock in the CURRENT graceful behaviors (verified by probing) so a future
refactor cannot silently replace "all-NaN warm-up" with an IndexError.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from techna.indicators.econometrics import (
    compute_hurst_exponent,
    compute_quantile_beta,
)
from techna.indicators.regime import compute_adx, compute_atr
from techna.indicators.trend import compute_ema, compute_sma


def test_sma_window_larger_than_data_is_all_nan():
    s = pd.Series([100.0, 101.0, 102.0, 101.0, 103.0])
    out = compute_sma(s, 20)
    assert len(out) == len(s)
    assert out.isna().all()          # warm-up only, never an exception


def test_ema_span_larger_than_data_stays_finite():
    s = pd.Series([100.0, 101.0, 102.0, 101.0, 103.0])
    out = compute_ema(s, 20)
    assert len(out) == len(s)
    # adjust=False EMA seeds from the first value, so it is defined everywhere.
    assert np.isfinite(out).all()


def test_adx_with_two_bars_returns_nan_not_crash():
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1e6, 1e6],
        },
        index=pd.date_range("2024-01-02", periods=2, freq="D"),
    )
    adx = compute_adx(df, 14)
    assert len(adx) == 2
    assert adx["adx"].isna().all()
    assert compute_atr(df, 14).isna().all()


def test_hurst_on_tiny_series_returns_neutral_default():
    res = compute_hurst_exponent(pd.Series([0.01, -0.01, 0.02]))
    # Too little data to estimate anything: neutral 0.5 / random_walk default,
    # never a crash or a fake confident estimate.
    assert res["hurst"] == 0.5
    assert res["state_label"] == "random_walk"


def test_quantile_beta_on_degenerate_input_reports_n():
    res = compute_quantile_beta(pd.Series([0.01]), pd.Series([0.01]))
    # No crash; the honest part is that n is carried so a consumer can see
    # the estimate is meaningless.
    assert res["n"] == 1
    assert "state_label" in res
