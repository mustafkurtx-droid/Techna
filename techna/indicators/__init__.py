"""Indicator package.

Each indicator here is a PURE function:
    compute_<name>(prices: pd.Series, ...) -> pd.Series | pd.DataFrame
"""
from __future__ import annotations

from techna.indicators.trend import (
    compute_ema,
    compute_sma,
    detect_cross,
    trend_state,
)
from techna.indicators.momentum import (
    compute_rsi,
    compute_macd,
    rsi_state,
    macd_state,
    compute_stochastic,
    stochastic_state,
)
from techna.indicators.volatility import (
    compute_bollinger,
    bollinger_state,
)
from techna.indicators.levels import (
    find_support_resistance,
    cluster_levels,
    rank_levels,
    select_levels,
)
from techna.indicators.regime import (
    compute_atr,
    compute_adx,
    trend_regime,
    volatility_regime,
)
from techna.indicators.divergence import (
    detect_divergence,
    find_swings,
)
from techna.indicators.baserates import (
    forward_return,
    conditional_stats,
    baseline_stats,
)
from techna.indicators.relative import (
    align_close,
    relative_strength,
    rebased_performance,
    rs_state,
)
from techna.indicators.seasonality import (
    monthly_returns,
    seasonality_table,
    monthly_summary,
)
from techna.indicators.volume import (
    compute_obv,
    detect_obv_divergence,
    compute_vwap,
    vwap_state,
    compute_mfi,
    mfi_state,
    compute_avwap,
)
from techna.indicators.econometrics import (
    compute_acf_pacf,
    compute_return_distribution_stats,
    compute_stationarity_tests,
    cusum_instability_test,
    detect_structural_breaks,
    compute_hurst_exponent,
    compute_hurst_analysis,
    compute_quantile_beta,
    compute_regime_conditional_stats,
    ljung_box_test,
    variance_ratio_test,
    distribution_uncertainty,
)
from techna.indicators.risk_context import (
    compute_52week_range,
    compute_drawdown_series,
    find_drawdown_episodes,
    compute_liquidity_metrics,
    compute_beta,
)
from techna.indicators.mtf import (
    compute_weekly_context,
    resample_to_weekly,
)
from techna.indicators.events import (
    compute_events,
)
from techna.indicators.volume_profile import (
    compute_volume_profile,
)
from techna.indicators.squeeze import (
    compute_squeeze,
)
from techna.indicators.volume_profile_weekly import (
    compute_volume_profile_weekly,
)
from techna.indicators.fibonacci import (
    compute_fibonacci,
)
from techna.indicators.donchian import (
    compute_donchian,
)
from techna.indicators.candles import (
    compute_candle_patterns,
)

__all__ = [
    "compute_sma",
    "compute_ema",
    "detect_cross",
    "trend_state",
    "compute_rsi",
    "compute_macd",
    "rsi_state",
    "macd_state",
    "compute_stochastic",
    "stochastic_state",
    "compute_bollinger",
    "bollinger_state",
    "find_support_resistance",
    "cluster_levels",
    "rank_levels",
    "select_levels",
    "compute_atr",
    "compute_adx",
    "trend_regime",
    "volatility_regime",
    "detect_divergence",
    "find_swings",
    "forward_return",
    "conditional_stats",
    "baseline_stats",
    "align_close",
    "relative_strength",
    "rebased_performance",
    "rs_state",
    "monthly_returns",
    "seasonality_table",
    "monthly_summary",
    "compute_obv",
    "detect_obv_divergence",
    "compute_vwap",
    "vwap_state",
    "compute_acf_pacf",
    "compute_return_distribution_stats",
    "compute_stationarity_tests",
    "cusum_instability_test",
    "detect_structural_breaks",
    "compute_hurst_exponent",
    "compute_hurst_analysis",
    "compute_quantile_beta",
    "compute_regime_conditional_stats",
    "ljung_box_test",
    "variance_ratio_test",
    "distribution_uncertainty",
    "compute_52week_range",
    "compute_drawdown_series",
    "find_drawdown_episodes",
    "compute_liquidity_metrics",
    "compute_beta",
    "compute_weekly_context",
    "resample_to_weekly",
    "compute_events",
    "compute_volume_profile",
    "compute_squeeze",
    "compute_volume_profile_weekly",
    "compute_fibonacci",
    "compute_donchian",
    "compute_mfi",
    "mfi_state",
    "compute_avwap",
    "compute_candle_patterns",
]
