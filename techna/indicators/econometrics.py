"""Econometric indicators module.

Provides ACF/PACF autocorrelation analysis and normality/distribution fit tests.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.stats
import statsmodels.tsa.stattools as stattools

from techna import config


def compute_acf_pacf(returns: pd.Series, lags: int = config.ACF_LAGS) -> dict:
    """Calculate ACF/PACF for raw returns, absolute returns, and squared returns."""
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas.Series")
        
    N = len(returns)
    if N < 2:
        return {
            "raw": {"acf": [1.0], "pacf": [1.0]},
            "abs": {"acf": [1.0], "pacf": [1.0]},
            "sq": {"acf": [1.0], "pacf": [1.0]},
            "conf": 0.0,
            "raw_autocorrelation_detected": False,
            "raw_significant_early_lags": [],
            "volatility_clustering_detected": False,
        }
        
    # Cap lags if length of returns is too small
    actual_lags = min(lags, N - 1)
    
    # Calculate ACF and PACF for raw, absolute, and squared returns
    acf_raw = stattools.acf(returns, nlags=actual_lags, fft=False)
    pacf_raw = stattools.pacf(returns, nlags=actual_lags, method="ywm")
    
    abs_ret = returns.abs()
    acf_abs = stattools.acf(abs_ret, nlags=actual_lags, fft=False)
    pacf_abs = stattools.pacf(abs_ret, nlags=actual_lags, method="ywm")
    
    sq_ret = returns ** 2
    acf_sq = stattools.acf(sq_ret, nlags=actual_lags, fft=False)
    pacf_sq = stattools.pacf(sq_ret, nlags=actual_lags, method="ywm")
    
    # 95% Confidence Interval band (White-Noise Null)
    conf = 1.96 / np.sqrt(N)

    # Both findings below restrict themselves to the EARLY-lag window. Scanning
    # all `lags` lags would yield ~5% false crossings by chance (multiple
    # comparisons), so we require at least ACF_MIN_SIGNIFICANT significant lags
    # within the first ACF_EARLY_LAGS. Raw and clustering use the SAME discipline.
    early_limit = min(actual_lags, config.ACF_EARLY_LAGS) if actual_lags >= 1 else 0

    # Raw-returns autocorrelation (two-sided: momentum or mean-reversion).
    raw_significant_early_lags = [
        lag for lag in range(1, early_limit + 1) if abs(acf_raw[lag]) > conf
    ]
    raw_autocorrelation_detected = (
        len(raw_significant_early_lags) >= config.ACF_MIN_SIGNIFICANT
    )

    # Volatility clustering (one-sided positive) on squared returns.
    volatility_clustering_detected = False
    if actual_lags >= 1:
        sq_early = acf_sq[1:early_limit + 1]
        sig_count = int(np.sum(sq_early > conf))
        volatility_clustering_detected = bool(
            acf_sq[1] > conf and sig_count >= config.ACF_MIN_SIGNIFICANT
        )

    return {
        "raw": {"acf": list(acf_raw), "pacf": list(pacf_raw)},
        "abs": {"acf": list(acf_abs), "pacf": list(pacf_abs)},
        "sq": {"acf": list(acf_sq), "pacf": list(pacf_sq)},
        "conf": float(conf),
        "raw_autocorrelation_detected": raw_autocorrelation_detected,
        "raw_significant_early_lags": raw_significant_early_lags,
        "volatility_clustering_detected": volatility_clustering_detected,
    }


def compute_return_distribution_stats(returns: pd.Series) -> dict:
    """Compute distribution moments (skewness, excess kurtosis), Jarque-Bera statistic, and parameter fits."""
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas.Series")
        
    N = len(returns)
    if N < 2:
        return {
            "skew": 0.0,
            "excess_kurtosis": 0.0,
            "jb_stat": 0.0,
            "jb_pvalue": 1.0,
            "is_normal": True,
            "normal_fit": {"loc": 0.0, "scale": 0.0},
            "t_fit": {"df": 1.0, "loc": 0.0, "scale": 0.0},
            "n": N,
        }
        
    skew = float(scipy.stats.skew(returns, bias=True))
    exc_kurt = float(scipy.stats.kurtosis(returns, fisher=True, bias=True))
    jb_stat, jb_p = scipy.stats.jarque_bera(returns)
    
    mean_val = float(returns.mean())
    std_val = float(returns.std(ddof=0))
    
    # Fit student-t
    t_params = scipy.stats.t.fit(returns)
    
    return {
        "skew": skew,
        "excess_kurtosis": exc_kurt,
        "jb_stat": float(jb_stat),
        "jb_pvalue": float(jb_p),
        "is_normal": bool(jb_p >= 0.05),
        "normal_fit": {"loc": mean_val, "scale": std_val},
        "t_fit": {"df": float(t_params[0]), "loc": float(t_params[1]), "scale": float(t_params[2])},
        "n": N,
    }


def stationarity_verdict(adf_decision: str, kpss_decision: str) -> str:
    """Combine ADF (H0=unit root) and KPSS (H0=stationary) decisions into a label.

    ADF and KPSS have OPPOSITE nulls, so the four decision combinations map to:
      ADF reject + KPSS fail-to-reject -> stationary
      ADF fail   + KPSS reject         -> non-stationary (unit root / random walk)
      ADF reject + KPSS reject         -> difference-stationary / possibly fractional
      ADF fail   + KPSS fail-to-reject -> inconclusive / trend-stationary
    """
    adf_reject = adf_decision == "reject H0"
    kpss_reject = kpss_decision == "reject H0"
    if adf_reject and not kpss_reject:
        return "stationary"
    if not adf_reject and kpss_reject:
        return "non-stationary (unit root / random walk)"
    if adf_reject and kpss_reject:
        return "difference-stationary / possibly fractional"
    return "inconclusive / trend-stationary"


def compute_stationarity_tests(series: pd.Series, regression: str = "c") -> dict:
    """Run ADF and KPSS stationarity tests on a series and determine combined verdict."""
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas.Series")
        
    clean_series = series.dropna()
    N = len(clean_series)
    if N < 10:
        return {
            "adf": {"stat": 0.0, "pvalue": 1.0, "crit": {}, "decision": "fail to reject"},
            "kpss": {"stat": 0.0, "pvalue": 1.0, "crit": {}, "decision": "fail to reject"},
            "state_label": "inconclusive / trend-stationary",
        }
        
    # ADF test
    adf_res = stattools.adfuller(clean_series, autolag="AIC")
    adf_stat = float(adf_res[0])
    adf_p = float(adf_res[1])
    adf_crit = {k: float(v) for k, v in adf_res[4].items()}
    adf_decision = "reject H0" if adf_p < 0.05 else "fail to reject"
    
    # KPSS test (suppress interpolation warnings)
    import warnings
    from statsmodels.tools.sm_exceptions import InterpolationWarning
    
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=InterpolationWarning)
        kpss_res = stattools.kpss(clean_series, regression=regression, nlags="auto")
        
    kpss_stat = float(kpss_res[0])
    kpss_p = float(kpss_res[1])
    kpss_crit = {k: float(v) for k, v in kpss_res[3].items()}
    kpss_decision = "reject H0" if kpss_p < 0.05 else "fail to reject"
    
    state_label = stationarity_verdict(adf_decision, kpss_decision)

    return {
        "adf": {
            "stat": adf_stat,
            "pvalue": adf_p,
            "crit": adf_crit,
            "decision": adf_decision,
        },
        "kpss": {
            "stat": kpss_stat,
            "pvalue": kpss_p,
            "crit": kpss_crit,
            "decision": kpss_decision,
        },
        "state_label": state_label,
    }


def cusum_instability_test(returns: pd.Series) -> dict:
    """Run parameter stability CUSUM test on constant OLS residuals.
    
    H0 = Parameter stability (no structural changes).
    """
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas.Series")
        
    clean_ret = returns.dropna()
    N = len(clean_ret)
    if N < 10:
        return {
            "stat": 0.0,
            "pvalue": 1.0,
            "unstable": False,
        }
        
    from statsmodels.stats.diagnostic import breaks_cusumolsresid
    
    mean_val = clean_ret.mean()
    resid = (clean_ret - mean_val).values
    
    sup_b, pval, _ = breaks_cusumolsresid(resid, ddof=1)
    
    return {
        "stat": float(sup_b),
        "pvalue": float(pval),
        "unstable": bool(pval < 0.05),
    }


def detect_structural_breaks(
    returns: pd.Series,
    *,
    min_seg: int = config.BREAK_MIN_SEG,
    max_breaks: int = config.BREAK_MAX,
) -> list[dict]:
    """Detect structural breaks using Gaussian Likelihood Ratio binary segmentation."""
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas.Series")
        
    clean_ret = returns.dropna()
    N = len(clean_ret)
    if N < 2 * min_seg:
        return []
        
    breaks: list[dict] = []
    
    def _find_breaks(start_idx: int, end_idx: int) -> None:
        n = end_idx - start_idx
        if n < 2 * min_seg or len(breaks) >= max_breaks:
            return
            
        segment = clean_ret.values[start_idx:end_idx]
        var_full = max(1e-15, float(np.var(segment)))
        
        best_t = -1
        best_lr = -float("inf")
        
        for t in range(min_seg, n - min_seg + 1):
            var_left = max(1e-15, float(np.var(segment[:t])))
            var_right = max(1e-15, float(np.var(segment[t:])))
            
            lr = n * np.log(var_full) - (t * np.log(var_left) + (n - t) * np.log(var_right))
            if lr > best_lr:
                best_lr = lr
                best_t = t
                
        if best_lr > config.BREAK_MIN_STRENGTH:
            global_break_idx = start_idx + best_t
            
            left_segment = clean_ret.values[start_idx:global_break_idx]
            right_segment = clean_ret.values[global_break_idx:end_idx]
            
            mean_before = float(np.mean(left_segment))
            mean_after = float(np.mean(right_segment))
            var_before = float(np.var(left_segment))
            var_after = float(np.var(right_segment))
            
            var_ratio = max(var_before / max(1e-15, var_after), var_after / max(1e-15, var_before))
            is_vol_shift = bool(var_ratio >= config.BREAK_VAR_RATIO)
            
            mean_diff = abs(mean_after - mean_before)
            std_before = max(1e-15, np.sqrt(var_before))
            is_mean_shift = bool((mean_diff / std_before) >= config.BREAK_MEAN_STD_DEV)
            
            if is_vol_shift and is_mean_shift:
                shift_type = "both"
            elif is_vol_shift:
                shift_type = "volatility_shift"
            elif is_mean_shift:
                shift_type = "mean_shift"
            else:
                shift_type = "volatility_shift"
                
            break_date = clean_ret.index[global_break_idx]
            date_str = break_date.strftime("%Y-%m-%d") if hasattr(break_date, "strftime") else str(break_date)
            
            breaks.append({
                "date": date_str,
                "index": int(global_break_idx),
                "type": shift_type,
                "var_before": var_before,
                "var_after": var_after,
                "mean_before": mean_before,
                "mean_after": mean_after,
                "lr": float(best_lr),
            })
            
            # Recurse left and right
            _find_breaks(start_idx, global_break_idx)
            _find_breaks(global_break_idx, end_idx)
            
    _find_breaks(0, N)
    
    breaks.sort(key=lambda x: x["index"])
    return breaks[:max_breaks]


def compute_hurst_exponent(series: pd.Series) -> dict:
    """Compute R/S rescaled range Hurst exponent for a time series."""
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas.Series")
        
    clean_series = series.dropna()
    N = len(clean_series)
    
    min_scale = config.HURST_MIN_SCALE
    max_scale = N // 2
    if N < 20 or max_scale <= min_scale:
        return {
            "hurst": 0.5,
            "method": "R/S",
            "state_label": "random_walk",
            "scales": [],
            "rs_values": [],
        }
        
    # Generate log-spaced scales
    raw_scales = np.unique(np.logspace(np.log10(min_scale), np.log10(max_scale), num=10, dtype=int))
    scales = [int(s) for s in raw_scales if s >= min_scale and s <= max_scale]
    
    r = clean_series.values
    avg_rs = []
    actual_scales = []
    
    for n in scales:
        K = N // n
        rs_list = []
        for k in range(K):
            window = r[k*n : (k+1)*n]
            mean_w = np.mean(window)
            y = window - mean_w
            Z = np.cumsum(y)
            R = np.max(Z) - np.min(Z)
            S = np.std(window, ddof=0)
            if S > 1e-12:
                rs_list.append(R / S)
        if rs_list:
            avg_rs.append(np.mean(rs_list))
            actual_scales.append(n)
            
    if len(actual_scales) < 2:
        return {
            "hurst": 0.5,
            "method": "R/S",
            "state_label": "random_walk",
            "scales": [],
            "rs_values": [],
        }
        
    H = float(np.polyfit(np.log(actual_scales), np.log(avg_rs), 1)[0])
    
    # State label classification
    if H > config.HURST_PERSIST:
        state_label = "persistent_trending"
    elif H < config.HURST_MEANREV:
        state_label = "mean_reverting"
    else:
        state_label = "random_walk"
        
    return {
        "hurst": H,
        "method": "R/S",
        "state_label": state_label,
        "scales": [int(s) for s in actual_scales],
        "rs_values": [float(v) for v in avg_rs],
    }


def compute_hurst_analysis(returns: pd.Series) -> dict:
    """Compute rescaled range Hurst exponent for both returns and volatility (squared returns)."""
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas.Series")
        
    ret_h = compute_hurst_exponent(returns)
    vol_h = compute_hurst_exponent(returns ** 2)
    
    return {
        "returns": ret_h,
        "volatility": vol_h,
    }


def compute_quantile_beta(
    stock_returns: pd.Series,
    benchmark_returns: pd.Series,
    quantiles: list[float] = config.QBETA_QUANTILES,
) -> dict:
    """Compute quantile regression beta slopes and confidence intervals."""
    if not isinstance(stock_returns, pd.Series):
        raise TypeError("stock_returns must be a pandas.Series")
    if not isinstance(benchmark_returns, pd.Series):
        raise TypeError("benchmark_returns must be a pandas.Series")
        
    # Align returns on common timestamps
    df_aligned = pd.DataFrame({"stock": stock_returns, "bench": benchmark_returns}).dropna()
    N = len(df_aligned)
    if N < 20:
        # Fallback if too few data points
        return {
            "quantiles": quantiles,
            "betas": {q: 1.0 for q in quantiles},
            "cis": {q: [0.8, 1.2] for q in quantiles},
            "ols_beta": 1.0,
            "state_label": "symmetric_beta",
            "asymmetry_significant": False,
            "n": N,
        }
        
    from statsmodels.regression.quantile_regression import QuantReg
    from statsmodels.tools.tools import add_constant
    from techna.indicators.risk_context import compute_beta
    
    Y = df_aligned["stock"]
    X = add_constant(df_aligned["bench"])
    
    ols_res = compute_beta(df_aligned["stock"], df_aligned["bench"])
    ols_beta = ols_res["beta"]
    
    betas = {}
    cis = {}
    
    for q in quantiles:
        try:
            model = QuantReg(Y, X).fit(q=q)
            beta_q = float(model.params["bench"])
            ci_low, ci_high = model.conf_int().loc["bench"]
            betas[q] = beta_q
            cis[q] = [float(ci_low), float(ci_high)]
        except Exception:
            # Fallback to OLS beta if QuantReg fit fails
            betas[q] = ols_beta
            cis[q] = [ols_beta - 0.2, ols_beta + 0.2]
    
    # Asymmetry classification
    q_low = min(quantiles)
    q_high = max(quantiles)
    diff = betas[q_low] - betas[q_high]
    
    if diff > config.QBETA_ASYM_THRESHOLD:
        state_label = "downside_sensitive"
    elif diff < -config.QBETA_ASYM_THRESHOLD:
        state_label = "upside_sensitive"
    else:
        state_label = "symmetric_beta"

    # Honesty check: the classification above uses POINT estimates, but we also
    # compute CIs — so say whether the tail asymmetry is statistically
    # distinguishable. Deterministic proxy: the two tail CIs must be disjoint
    # in the direction of the claimed asymmetry. Overlapping CIs mean the
    # asymmetry is a point-estimate finding only (mirrors the bootstrap-CI
    # treatment of skew/kurtosis).
    if state_label == "downside_sensitive":
        asymmetry_significant = bool(cis[q_low][0] > cis[q_high][1])
    elif state_label == "upside_sensitive":
        asymmetry_significant = bool(cis[q_high][0] > cis[q_low][1])
    else:
        asymmetry_significant = False

    return {
        "quantiles": quantiles,
        "betas": betas,
        "cis": cis,
        "ols_beta": ols_beta,
        "state_label": state_label,
        "asymmetry_significant": asymmetry_significant,
        "n": N,
    }


def compute_regime_conditional_stats(returns: pd.Series, breaks: list[dict]) -> dict:
    """Compute and compare key statistics on the current post-break regime vs full-sample."""
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas.Series")
        
    clean_ret = returns.dropna()
    N_full = len(clean_ret)
    
    if N_full == 0:
        return {
            "is_split": False,
            "regime_start": "N/A",
            "n_full": 0,
            "n_regime": 0,
            "full": {"skew": float("nan"), "excess_kurtosis": float("nan"), "ann_vol": float("nan")},
            "regime": {"skew": float("nan"), "excess_kurtosis": float("nan"), "ann_vol": float("nan")},
            "regime_too_short": False,
        }
        
    if not breaks:
        is_split = False
        regime_start_val = clean_ret.index[0]
        regime_start = regime_start_val.strftime("%Y-%m-%d") if hasattr(regime_start_val, "strftime") else str(regime_start_val)
        regime_returns = clean_ret
    else:
        is_split = True
        last_idx = breaks[-1]["index"]
        if last_idx >= N_full:
            last_idx = N_full - 1
        regime_returns = clean_ret.iloc[last_idx:]
        regime_start_val = clean_ret.index[last_idx]
        regime_start = regime_start_val.strftime("%Y-%m-%d") if hasattr(regime_start_val, "strftime") else str(regime_start_val)
        
    N_regime = len(regime_returns)
    regime_too_short = bool(N_regime < config.REGIME_MIN_OBS)
    
    # Compute full stats
    full_dist = compute_return_distribution_stats(clean_ret)
    full_vol = float(clean_ret.std(ddof=1) * np.sqrt(252)) if N_full > 1 else float("nan")
    
    # Compute regime stats
    regime_dist = compute_return_distribution_stats(regime_returns)
    regime_vol = float(regime_returns.std(ddof=1) * np.sqrt(252)) if N_regime > 1 else float("nan")
    
    return {
        "is_split": is_split,
        "regime_start": regime_start,
        "n_full": N_full,
        "n_regime": N_regime,
        "full": {
            "skew": full_dist["skew"],
            "excess_kurtosis": full_dist["excess_kurtosis"],
            "ann_vol": full_vol,
        },
        "regime": {
            "skew": regime_dist["skew"],
            "excess_kurtosis": regime_dist["excess_kurtosis"],
            "ann_vol": regime_vol,
        },
        "regime_too_short": regime_too_short,
    }


def ljung_box_test(returns: pd.Series, lags: int = config.LJUNGBOX_LAGS) -> dict:
    """Perform Ljung-Box Q test for joint autocorrelation."""
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas.Series")
        
    clean_ret = returns.dropna()
    N = len(clean_ret)
    
    if N < 2:
        return {
            "lags": lags,
            "lb_stat": 0.0,
            "lb_pvalue": 1.0,
            "significant": False,
        }
        
    actual_lags = min(lags, N - 1)
    if actual_lags < 1:
        return {
            "lags": lags,
            "lb_stat": 0.0,
            "lb_pvalue": 1.0,
            "significant": False,
        }
        
    from statsmodels.stats.diagnostic import acorr_ljungbox
    res = acorr_ljungbox(clean_ret, lags=[actual_lags], return_df=True)
    lb_stat = float(res["lb_stat"].iloc[0])
    lb_p = float(res["lb_pvalue"].iloc[0])
    
    return {
        "lags": actual_lags,
        "lb_stat": lb_stat,
        "lb_pvalue": lb_p,
        "significant": bool(lb_p < 0.05),
    }


def variance_ratio_test(returns: pd.Series, q_values: list[int] = config.VR_Q_VALUES) -> dict:
    """Perform Lo-MacKinlay (1988) heteroskedasticity-robust Variance Ratio test using overlapping windows."""
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas.Series")
        
    clean_ret = returns.dropna()
    N = len(clean_ret)
    
    vr_dict = {}
    zstat_dict = {}
    pvalue_dict = {}
    verdicts = {}
    
    vals = clean_ret.values
    mu = np.mean(vals) if N > 0 else 0.0
    sigma2_a = np.var(vals, ddof=1) if N > 1 else 0.0
    
    diff = vals - mu
    diff_sq = diff ** 2
    denom = np.sum(diff_sq) ** 2
    
    for q in q_values:
        if N < q or q < 2 or sigma2_a < 1e-15:
            vr_dict[q] = 1.0
            zstat_dict[q] = 0.0
            pvalue_dict[q] = 1.0
            verdicts[q] = "random walk"
            continue
            
        # Compute sigma2_c with overlapping window
        rolling_sum = clean_ret.rolling(window=q).sum().dropna().values
        sum_diff_sq = np.sum((rolling_sum - q * mu) ** 2)
        m = q * (N - q + 1) * (1.0 - q / N)
        sigma2_c = sum_diff_sq / m
        vr = sigma2_c / sigma2_a
        vr_dict[q] = float(vr)
        
        # Compute delta(j) for j=1..q-1
        theta = 0.0
        for j in range(1, q):
            numerator = np.sum(diff_sq[j:] * diff_sq[:-j])
            delta_j = numerator / denom if denom > 1e-30 else 0.0
            weight = (2.0 * (q - j) / q) ** 2
            theta += weight * delta_j
            
        if theta < 1e-15:
            zstat = 0.0
            p_val = 1.0
        else:
            zstat = (vr - 1.0) / np.sqrt(theta)
            p_val = 2.0 * (1.0 - scipy.stats.norm.cdf(abs(zstat)))
            
        zstat_dict[q] = float(zstat)
        pvalue_dict[q] = float(p_val)
        
        # Verdict
        if abs(zstat) < 1.96:
            verdicts[q] = "random walk"
        elif vr > 1.0:
            verdicts[q] = "trending (positive autocorr)"
        else:
            verdicts[q] = "mean-reverting"
            
    lowest_q = min(q_values) if q_values else 2
    state_label = verdicts.get(lowest_q, "random walk")
    
    return {
        "q_values": q_values,
        "vr": vr_dict,
        "zstat": zstat_dict,
        "pvalue": pvalue_dict,
        "window": "overlapping",
        "state_label": state_label,
    }


def distribution_uncertainty(
    returns: pd.Series,
    *,
    n_boot: int = config.BOOT_N,
    seed: int = config.BOOT_SEED,
) -> dict:
    """Estimate bootstrap confidence intervals for return skewness and kurtosis."""
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas.Series")
        
    clean_ret = returns.dropna()
    vals = clean_ret.values
    n = len(vals)
    
    if n < 5:
        return {
            "skew_ci": [float("nan"), float("nan")],
            "kurtosis_ci": [float("nan"), float("nan")],
            "n_boot": n_boot,
        }
        
    rs = np.random.RandomState(seed)
    boot_skews = np.empty(n_boot)
    boot_kurts = np.empty(n_boot)
    
    for i in range(n_boot):
        idx = rs.randint(0, n, size=n)
        sample = vals[idx]
        boot_skews[i] = scipy.stats.skew(sample, bias=True)
        boot_kurts[i] = scipy.stats.kurtosis(sample, fisher=True, bias=True)
        
    skew_low, skew_high = np.percentile(boot_skews, [2.5, 97.5])
    kurt_low, kurt_high = np.percentile(boot_kurts, [2.5, 97.5])
    
    return {
        "skew_ci": [float(skew_low), float(skew_high)],
        "kurtosis_ci": [float(kurt_low), float(kurt_high)],
        "n_boot": n_boot,
    }
