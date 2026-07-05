"""Offline tests for Econometric Analysis (validates econometrics.feature)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from techna.indicators.econometrics import compute_acf_pacf, compute_return_distribution_stats

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "golden_returns.csv"


@pytest.fixture
def golden_returns() -> pd.Series:
    """Load stable i.i.d. golden returns from fixture."""
    df = pd.read_csv(FIXTURE_PATH, index_col=0, parse_dates=True)
    return df["Return"]


def test_acf_calculation_accuracy(golden_returns):
    """Scenario: ACF matches an independent direct-formula computation at early lags.
    
    Verification method:
    acf(k) = sum_{t=k}^{N-1} (r_t - r_mean)*(r_{t-k} - r_mean) / sum_{t=0}^{N-1} (r_t - r_mean)^2
    And PACF[1] == ACF[1] always.
    """
    res = compute_acf_pacf(golden_returns, lags=10)
    
    # 1. Independent direct formula calculation
    r = golden_returns.values
    r_mean = np.mean(r)
    denom = np.sum((r - r_mean) ** 2)
    
    # Lag 1
    num1 = np.sum((r[1:] - r_mean) * (r[:-1] - r_mean))
    expected_acf1 = num1 / denom
    
    # Lag 2
    num2 = np.sum((r[2:] - r_mean) * (r[:-2] - r_mean))
    expected_acf2 = num2 / denom
    
    # Verify lag 0 is 1.0
    assert res["raw"]["acf"][0] == pytest.approx(1.0)
    assert res["raw"]["acf"][1] == pytest.approx(expected_acf1, rel=1e-7)
    assert res["raw"]["acf"][2] == pytest.approx(expected_acf2, rel=1e-7)
    
    # 2. Assert PACF[1] == ACF[1]
    # In statsmodels acf/pacf outputs:
    # acf[0] = 1.0, pacf[0] = 1.0.
    # acf[1] == pacf[1].
    assert res["raw"]["pacf"][1] == pytest.approx(res["raw"]["acf"][1], rel=1e-7)


def test_volatility_clustering_detection(golden_returns):
    """Scenario: Volatility clustering is detected for clustered series, but not for i.i.d."""
    # 1. Volatility Clustering: high variance block followed by low variance block.
    # This leads to high positive autocorrelation in absolute and squared returns.
    high_var = [0.05, -0.05, 0.04, -0.04] * 20
    low_var = [0.001, -0.001, 0.002, -0.002] * 20
    returns_clustered = pd.Series(high_var + low_var)
    
    res_clustered = compute_acf_pacf(returns_clustered, lags=10)
    assert res_clustered["volatility_clustering_detected"] is True
    
    # 2. No Volatility Clustering (i.i.d. golden returns)
    res_iid = compute_acf_pacf(golden_returns, lags=10)
    assert res_iid["volatility_clustering_detected"] is False


def test_raw_autocorrelation_early_lag_discipline(golden_returns):
    """Scenario: Raw-returns autocorrelation uses the same early-lag discipline as clustering.

    Avoids full 40-lag multiple-comparison false positives: i.i.d. returns are
    reported as a random walk; a genuinely autocorrelated series is flagged.
    """
    # i.i.d. golden returns -> no early-lag autocorrelation (random walk)
    res_iid = compute_acf_pacf(golden_returns, lags=40)
    assert res_iid["raw_autocorrelation_detected"] is False

    # Deterministic strongly-autocorrelated series (sine) -> detected at early lags
    autocorr = pd.Series(np.sin(np.linspace(0, 6 * np.pi, 100)))
    res_ac = compute_acf_pacf(autocorr, lags=10)
    assert res_ac["raw_autocorrelation_detected"] is True
    assert len(res_ac["raw_significant_early_lags"]) >= 2


def test_skewness_kurtosis_accuracy(golden_returns):
    """Scenario: Skewness and excess kurtosis match independent moment formulas.
    
    Moment formulas (bias=True, fisher=True):
    m_k = (1/n) * sum((x - mean)^k)
    skew = m3 / m2^1.5
    exc_kurt = m4 / m2^2 - 3
    """
    res = compute_return_distribution_stats(golden_returns)
    
    # Independent moment formulas
    x = golden_returns.values
    n = len(x)
    x_mean = np.mean(x)
    m2 = np.sum((x - x_mean) ** 2) / n
    m3 = np.sum((x - x_mean) ** 3) / n
    m4 = np.sum((x - x_mean) ** 4) / n
    
    expected_skew = m3 / (m2 ** 1.5)
    expected_kurt = (m4 / (m2 ** 2)) - 3.0
    
    assert res["skew"] == pytest.approx(expected_skew, rel=1e-7)
    assert res["excess_kurtosis"] == pytest.approx(expected_kurt, rel=1e-7)


def test_jarque_bera_accuracy(golden_returns):
    """Scenario: Jarque-Bera matches an independent computation from skew/kurtosis.
    
    JB = (n/6) * (S^2 + 0.25 * K^2)
    """
    res = compute_return_distribution_stats(golden_returns)
    
    # Independent calculation from skew/kurtosis
    n = res["n"]
    skew = res["skew"]
    kurt = res["excess_kurtosis"]
    expected_jb = (n / 6.0) * (skew ** 2 + 0.25 * (kurt ** 2))
    
    assert res["jb_stat"] == pytest.approx(expected_jb, rel=1e-7)
    
    # Jarque-Bera p-value from chi2(df=2)
    # expected_p = 1 - chi2.cdf(expected_jb, 2)
    expected_p = np.exp(-expected_jb / 2.0)  # chi2(2) survival function is e^(-x/2)
    assert res["jb_pvalue"] == pytest.approx(expected_p, rel=1e-7)
