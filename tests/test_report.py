"""Offline tests for Report Generation (validates report.feature)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from techna import data_layer as dl
from techna.report_builder import build_report


def test_report_generation_workflow(golden_df, tmp_path):
    """Scenario: A markdown report and chart PNG are created properly."""
    # Mock analysis results
    price_data = dl.PriceData(
        ticker="TEST",
        df=golden_df,
        source="fixture",
        warnings=[],
    )
    
    trend_data = {
        "state": "uptrend",
        "sma50": pd.Series([100.0] * len(golden_df), index=golden_df.index),
        "sma200": pd.Series([90.0] * len(golden_df), index=golden_df.index),
        "last_cross": ("golden", "2024-01-10"),
    }
    
    momentum_data = {
        "last_rsi": 55.4,
        "rsi_state": "neutral",
        "macd_state": "bullish",
        "rsi": pd.Series([55.4] * len(golden_df), index=golden_df.index),
        "macd": pd.DataFrame(
            {
                "macd": [0.5] * len(golden_df),
                "signal": [0.2] * len(golden_df),
                "hist": [0.3] * len(golden_df),
            },
            index=golden_df.index,
        ),
        "last_macd": (0.5, 0.2, 0.3),
    }
    
    volatility_data = {
        "state": "within_bands",
        "upper": pd.Series([110.0] * len(golden_df), index=golden_df.index),
        "mid": pd.Series([100.0] * len(golden_df), index=golden_df.index),
        "lower": pd.Series([90.0] * len(golden_df), index=golden_df.index),
        "last_bands": (100.0, 110.0, 90.0, 0.5, 0.2),
    }
    
    levels_data = {
        "pivots": {
            "supports": [98.5, 99.0],
            "resistances": [105.0],
        },
        "support": pd.Series([float("nan")] * len(golden_df), index=golden_df.index),
        "resistance": pd.Series([float("nan")] * len(golden_df), index=golden_df.index),
        "v2": {
            "supports": [{"price": 98.5, "touches": 2}],
            "resistances": [{"price": 105.0, "touches": 1}],
        }
    }
    # Put a support pivot value at index 10 and resistance at index 20 to test plotting
    levels_data["support"].iloc[10] = 98.5
    levels_data["resistance"].iloc[20] = 105.0
    
    context_data = {
        "trend_regime": "trending_up",
        "volatility_regime": "normal",
        "last_atr": 4.51,
        "last_adx": 31.2,
        "divergence": {"bearish": False, "bullish": False, "detail": None},
        "baserates_stats": [
            {"horizon": 10, "condition": "Baseline", "n": 100, "win_rate": 0.55, "mean": 0.02, "median": 0.015, "reliable": True},
            {"horizon": 10, "condition": "RSI >= 70", "n": 15, "win_rate": 0.40, "mean": -0.01, "median": -0.005, "reliable": False},
        ],
        "baserates": {
            "fwd10": pd.Series([0.01] * len(golden_df), index=golden_df.index),
            "cond_rsi": pd.Series([False] * len(golden_df), index=golden_df.index),
            "cond_boll": pd.Series([False] * len(golden_df), index=golden_df.index),
        },
        "relative": {
            "benchmark_ticker": "SPY",
            "state": "outperforming",
            "rs": pd.Series([0.5] * len(golden_df), index=golden_df.index),
            "rs_ma": pd.Series([0.48] * len(golden_df), index=golden_df.index),
            "asset_rebased": pd.Series([100.0] * len(golden_df), index=golden_df.index),
            "bench_rebased": pd.Series([100.0] * len(golden_df), index=golden_df.index),
        },
        "seasonality_summary": pd.DataFrame(
            {"mean": [0.01] * 12, "win_rate": [0.5] * 12},
            index=list(range(1, 13))
        ),
        "seasonality_table": pd.DataFrame(
            [[0.01] * 12],
            index=[2024],
            columns=list(range(1, 13))
        ),
        "volume": {
            "vwap": pd.Series([100.0] * len(golden_df), index=golden_df.index),
            "obv": pd.Series([10000.0] * len(golden_df), index=golden_df.index),
            "divergence": {
                "state": "bullish_divergence",
                "price_slope": -0.05,
                "obv_slope": 50.0,
            },
            "state": {
                "state": "above_vwap",
                "distance_pct": 2.5,
            }
        },
        "econometrics": {
            "status": "ok",
            "acf_pacf": {
                "raw": {"acf": [1.0, 0.05, -0.02], "pacf": [1.0, 0.05, -0.02]},
                "abs": {"acf": [1.0, 0.08, 0.03], "pacf": [1.0, 0.08, 0.03]},
                "sq": {"acf": [1.0, 0.12, 0.06], "pacf": [1.0, 0.12, 0.06]},
                "conf": 0.15,
                "volatility_clustering_detected": False,
            },
            "distribution": {
                "skew": -0.15,
                "excess_kurtosis": 1.25,
                "jb_stat": 8.5,
                "jb_pvalue": 0.014,
                "is_normal": False,
                "normal_fit": {"loc": 0.0005, "scale": 0.015},
                "t_fit": {"df": 4.5, "loc": 0.0004, "scale": 0.012},
                "n": 250,
            },
            "stationarity_levels": {
                "adf": {"stat": -1.2, "pvalue": 0.65, "crit": {}, "decision": "fail to reject"},
                "kpss": {"stat": 0.5, "pvalue": 0.01, "crit": {}, "decision": "reject H0"},
                "state_label": "non-stationary (unit root / random walk)"
            },
            "stationarity_returns": {
                "adf": {"stat": -12.5, "pvalue": 0.0, "crit": {}, "decision": "reject H0"},
                "kpss": {"stat": 0.05, "pvalue": 0.1, "crit": {}, "decision": "fail to reject"},
                "state_label": "stationary"
            },
            "cusum": {
                "stat": 0.8,
                "pvalue": 0.45,
                "unstable": False
            },
            "breaks": [
                {
                    "date": "2024-01-15",
                    "index": 10,
                    "type": "volatility_shift",
                    "mean_before": 0.0,
                    "mean_after": 0.0,
                    "var_before": 0.01,
                    "var_after": 0.04,
                    "lr": 22.0
                }
            ],
            "hurst": {
                "returns": {
                    "hurst": 0.52,
                    "method": "R/S",
                    "state_label": "random_walk",
                    "scales": [8, 16, 32],
                    "rs_values": [1.5, 2.2, 3.1]
                },
                "volatility": {
                    "hurst": 0.68,
                    "method": "R/S",
                    "state_label": "persistent_trending",
                    "scales": [8, 16, 32],
                    "rs_values": [1.8, 2.9, 4.5]
                }
            },
            "quantile_beta": {
                "quantiles": [0.05, 0.50, 0.95],
                "betas": {0.05: 1.5, 0.50: 1.0, 0.95: 0.8},
                "cis": {0.05: [1.2, 1.8], 0.50: [0.9, 1.1], 0.95: [0.6, 1.0]},
                "ols_beta": 1.15,
                "state_label": "downside_sensitive",
                "n": 250
            },
            "regime_conditional": {
                "is_split": True,
                "regime_start": "2024-01-15",
                "n_full": 250,
                "n_regime": 240,
                "full": {"skew": 0.05, "excess_kurtosis": 1.25, "ann_vol": 0.15},
                "regime": {"skew": 0.02, "excess_kurtosis": 0.50, "ann_vol": 0.20},
                "regime_too_short": False,
            },
            "ljung_box": {
                "lags": 10,
                "lb_stat": 8.5,
                "lb_pvalue": 0.58,
                "significant": False,
            },
            "variance_ratio": {
                "q_values": [2, 4, 8, 16],
                "vr": {2: 1.05, 4: 1.10, 8: 1.15, 16: 1.20},
                "zstat": {2: 0.5, 4: 0.8, 8: 1.2, 16: 1.5},
                "pvalue": {2: 0.6, 4: 0.4, 8: 0.23, 16: 0.13},
                "window": "overlapping",
                "state_label": "random walk",
            },
            "dist_uncertainty": {
                "skew_ci": [-0.2, 0.3],
                "kurtosis_ci": [0.8, 1.8],
                "n_boot": 1000,
            }
        },
        "risk": {
            "status": "ok",
            "52week": {
                "high": 150.0,
                "low": 50.0,
                "current": 100.0,
                "position_pct": 50.0,
                "state": "mid_range",
                "window_used": 252,
            },
            "drawdown_series": pd.DataFrame({
                "close": [100.0] * len(golden_df),
                "running_max": [100.0] * len(golden_df),
                "drawdown": [0.0] * len(golden_df),
            }, index=golden_df.index),
            "drawdown_episodes": [
                {
                    "peak_date": "2024-01-02",
                    "trough_date": "2024-01-03",
                    "trough_pct": -0.10,
                    "recovery_date": "2024-01-04",
                    "days_to_recover": 1,
                }
            ],
            "liquidity": {
                "adv20": 1000000.0,
                "adv90": 950000.0,
                "avg_value_20": 10000000.0,
                "state": "moderate_liquidity",
            },
            "beta": {
                "beta": 1.15,
                "alpha_annualized": 0.05,
                "r_squared": 0.65,
                "state": "market_beta",
                "n": 250,
            },
            "stock_returns": pd.Series([0.01] * len(golden_df), index=golden_df.index),
            "bench_returns": pd.Series([0.01] * len(golden_df), index=golden_df.index),
        },
        "scores": {
            "trend_strength": {"value": 85, "rule_breakdown": ["Rule A", "Rule B"], "state_label": "strong"},
            "momentum": {"value": 65, "rule_breakdown": ["Rule C"], "state_label": "bullish"},
            "trend_maturity": {"value": 50, "rule_breakdown": ["Rule D"], "state_label": "mid", "description_note": "high maturity = less upside room, descriptive not bad"},
            "liquidity": {"value": 100, "rule_breakdown": ["Rule E"], "state_label": "high"},
            "volatility_level": {"value": 50, "rule_breakdown": ["Rule F"], "state_label": "normal", "description_note": "volatility level is descriptive, not inherently good or bad"},
            "statistical_edge": {"value": 50, "rule_breakdown": ["Rule G"], "state_label": "insufficient_sample", "reliable": False},
        }
    }

    # Generate report
    report_path_str = build_report(
        "TEST",
        price_data,
        trend_data,
        momentum_data,
        volatility_data,
        levels_data,
        context_data=context_data,
        out_dir=tmp_path,
        draw_chart=True,
        no_interactive=True,
    )
    
    report_path = Path(report_path_str)
    assert report_path.exists()
    assert report_path.name == "TEST_report.md"

    # Multiple focused charts are now produced (overview, momentum, regime, candles, levels, baserates, relative, seasonality, volume, correlogram, distribution, structural_breaks, hurst, quantile_beta, 52week, drawdown, beta).
    expected_charts = (
        "TEST_overview.png", "TEST_momentum.png", "TEST_candles.png", "TEST_levels.png",
        "TEST_baserates.png", "TEST_relative.png", "TEST_seasonality.png", "TEST_volume.png",
        "TEST_correlogram.png", "TEST_distribution.png", "TEST_structural_breaks.png",
        "TEST_hurst.png", "TEST_quantile_beta.png", "TEST_52week.png", "TEST_drawdown.png", "TEST_beta.png"
    )
    for name in expected_charts:
        chart_path = tmp_path / name
        assert chart_path.exists(), f"missing chart {name}"
        assert chart_path.stat().st_size > 0
    
    # Verify contents of markdown file
    content = report_path.read_text(encoding="utf-8")
    
    # 1. Check disclaimer
    assert "signals, not advice" in content.lower()
    
    # 2. Check sections exist
    assert "## 2. Trend Analysis" in content
    assert "## 3. Momentum Analysis" in content
    assert "## 4. Volatility (Bollinger Bands)" in content
    assert "## 5. Support & Resistance Levels" in content
    assert "## 6. Context & Regime" in content
    assert "## 6.6. Relative Strength vs Benchmark" in content
    assert "## 6.5. Empirical Base Rates" in content
    assert "## 6.7. Monthly Seasonality Summary" in content
    assert "## 6.8. Volume Analysis (OBV & VWAP)" in content
    assert "## 6.9. Predictability Analysis (ACF/PACF)" in content
    assert "## 6.10. Return Distribution Analysis" in content
    assert "## 1.5. At a Glance — Risk Context" in content
    assert "## 6.11. 52-Week Range Position" in content
    assert "## 6.12. Drawdown History" in content
    assert "## 6.13. Liquidity Assessment" in content
    assert "## 6.14. Systematic Risk (Beta)" in content
    assert "## 6.15. Score Profile (Independent Dimensions)" in content
    assert "## 6.16. Stationarity Analysis" in content
    assert "## 6.17. Structural Break Analysis" in content
    assert "## 6.18. Long Memory Analysis (Hurst Exponent)" in content
    assert "## 6.19. Conditional Beta (Quantile Regression)" in content
    assert "## 6.20. Variance Ratio (Lo-MacKinlay)" in content
    assert "## 7. Technical Chart" in content
    assert "trending_up" in content
    
    # 3. Check specific values are reported
    assert "uptrend" in content
    assert "55.40" in content
    assert "neutral" in content
    assert "98.50" in content
    assert "105.00" in content
    
    # Check new Phase 23 & 24 indicators values in text
    assert "Current Regime vs Full Sample Analysis" in content
    assert "Annualized Volatility" in content
    assert "Ljung-Box Joint Test" in content
    assert "variance ratio" in content.lower()
    assert "bootstrap ci" in content.lower()
    
    assert "TEST_overview.png" in content
    assert "TEST_momentum.png" in content
    assert "TEST_candles.png" in content
    assert "TEST_levels.png" in content
    assert "TEST_baserates.png" in content
    assert "TEST_relative.png" in content
    assert "TEST_seasonality.png" in content
    assert "TEST_volume.png" in content
    assert "TEST_correlogram.png" in content
    assert "TEST_distribution.png" in content
    assert "TEST_structural_breaks.png" in content
    assert "TEST_hurst.png" in content
    assert "TEST_quantile_beta.png" in content
    assert "TEST_52week.png" in content
    assert "TEST_drawdown.png" in content
    assert "TEST_beta.png" in content
