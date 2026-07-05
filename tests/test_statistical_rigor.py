"""Offline tests for Statistical Rigor package (validates specs/statistical_rigor.feature)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna.indicators.econometrics import (
    ljung_box_test,
    variance_ratio_test,
    distribution_uncertainty,
)


def test_ljung_box_iid_vs_ar1():
    """Verify Ljung-Box test on IID vs AR(1) series."""
    rs = np.random.RandomState(42)
    # IID returns
    iid = pd.Series(rs.normal(loc=0.0, scale=0.01, size=200))
    res_iid = ljung_box_test(iid, lags=10)
    assert res_iid["significant"] is False
    assert res_iid["lb_pvalue"] >= 0.05
    
    # AR(1) returns with phi = 0.6
    ar1 = np.zeros(200)
    ar1[0] = rs.normal()
    for i in range(1, 200):
        ar1[i] = 0.6 * ar1[i-1] + rs.normal(scale=0.01)
    
    ar1_series = pd.Series(ar1)
    res_ar1 = ljung_box_test(ar1_series, lags=10)
    assert res_ar1["significant"] is True
    assert res_ar1["lb_pvalue"] < 0.05


def test_variance_ratio_known_series():
    """Verify Variance Ratio states on Random Walk, Mean Reverting, and Trending series."""
    rs = np.random.RandomState(42)
    
    # 1. Random Walk (IID returns)
    rw_ret = pd.Series(rs.normal(loc=0.0, scale=0.01, size=200))
    res_rw = variance_ratio_test(rw_ret, q_values=[2, 4, 8])
    assert res_rw["state_label"] == "random walk"
    # overlapping window type check
    assert res_rw["window"] == "overlapping"
    
    # 2. Mean Reverting (strongly negative autocorrelated returns)
    mr_ret = np.zeros(200)
    mr_ret[0] = rs.normal(scale=0.01)
    for i in range(1, 200):
        mr_ret[i] = -0.7 * mr_ret[i-1] + rs.normal(scale=0.01)
    res_mr = variance_ratio_test(pd.Series(mr_ret), q_values=[2, 4, 8])
    assert res_mr["state_label"] == "mean-reverting"
    assert res_mr["vr"][2] < 1.0
    
    # 3. Trending (strongly positive autocorrelated returns)
    tr_ret = np.zeros(200)
    tr_ret[0] = rs.normal(scale=0.01)
    for i in range(1, 200):
        tr_ret[i] = 0.7 * tr_ret[i-1] + rs.normal(scale=0.01)
    res_tr = variance_ratio_test(pd.Series(tr_ret), q_values=[2, 4, 8])
    assert res_tr["state_label"] == "trending (positive autocorr)"
    assert res_tr["vr"][2] > 1.0


def test_variance_ratio_manual_anchor():
    """Verify Variance Ratio values against the N=6 manual mathematical anchor."""
    # Returns from manual calculation: [0.02, -0.01, 0.03, 0.01, -0.02, 0.02]
    returns = pd.Series([0.02, -0.01, 0.03, 0.01, -0.02, 0.02])
    res = variance_ratio_test(returns, q_values=[2])
    
    # VR(2) manual math yielded ~0.6327
    assert res["vr"][2] == pytest.approx(0.63274336)
    # Theta(2) manual math yielded ~0.089186
    # zstat manual math yielded ~-1.2297683
    assert res["zstat"][2] == pytest.approx(-1.22976834)
    assert res["pvalue"][2] == pytest.approx(0.21878387)
    assert res["state_label"] == "random walk"


def test_distribution_uncertainty_bootstrap():
    """Verify bootstrap confidence intervals contain standard normal properties and are reproducible."""
    rs = np.random.RandomState(42)
    returns = pd.Series(rs.normal(loc=0.0, scale=0.01, size=200))
    
    res1 = distribution_uncertainty(returns, n_boot=1000, seed=42)
    res2 = distribution_uncertainty(returns, n_boot=1000, seed=42)
    
    # Reproducible check
    assert res1["skew_ci"] == res2["skew_ci"]
    assert res1["kurtosis_ci"] == res2["kurtosis_ci"]
    
    # Standard normal returns should have skewness around 0 and excess kurtosis around 0.
    # Therefore, the 95% bootstrap confidence intervals should contain 0.0.
    skew_lo, skew_hi = res1["skew_ci"]
    kurt_lo, kurt_hi = res1["kurtosis_ci"]
    
    assert skew_lo < 0.0 < skew_hi
    assert kurt_lo < 0.0 < kurt_hi


def test_period_arg_and_tail_warning(monkeypatch, tmp_path):
    """Verify that --period is passed down to get_prices and insufficient tail data produces a warning."""
    import importlib.util
    from techna import data_layer as dl

    # Load techna.py dynamically
    spec = importlib.util.spec_from_file_location("techna_cli_test", "techna.py")
    assert spec is not None
    techna_cli = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(techna_cli)
    
    passed_period = None
    
    def mock_get_prices(ticker, *, period=None, **kwargs):
        nonlocal passed_period
        passed_period = period
        idx = pd.date_range("2024-01-01", periods=500, freq="D")
        df = pd.DataFrame(
            {
                "Open": [100.0] * 500,
                "High": [100.0] * 500,
                "Low": [100.0] * 500,
                "Close": [100.0] * 500,
                "Volume": [1000] * 500,
            },
            index=idx,
        )
        return dl.PriceData(ticker=ticker, df=df, source="fixture", warnings=[])
        
    monkeypatch.setattr(dl, "get_prices", mock_get_prices)
    
    exit_code = techna_cli.main(["TEST", "--period", "5y", "--no-chart", "--no-interactive", "--out", str(tmp_path)])
    
    assert exit_code == 0
    assert passed_period == "5y"
    
    report_file = tmp_path / "TEST_report.md"
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "history is short" in content.lower()

