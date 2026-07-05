"""Techna command-line entry point.

Calculates all indicators, saves a PDF/markdown report with a chart, and
displays a Rich dashboard summary on the terminal.

Usage:
    python techna.py THYAO.IS
    python techna.py AAPL --interval 1d
    python techna.py AAPL --no-chart
    python techna.py AAPL --out custom_reports/
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
import pandas as pd
import numpy as np

from techna import config
from techna import data_layer as dl
from techna import io_contract
from techna.indicators import (
    compute_events,
    compute_weekly_context,
    compute_volume_profile,
    compute_squeeze,
    compute_volume_profile_weekly,
    compute_fibonacci,
    compute_donchian,
    compute_candle_patterns,
    bollinger_state,
    compute_adx,
    compute_atr,
    compute_bollinger,
    compute_sma,
    compute_macd,
    compute_rsi,
    detect_cross,
    detect_divergence,
    find_support_resistance,
    select_levels,
    macd_state,
    rsi_state,
    trend_regime,
    trend_state,
    volatility_regime,
    forward_return,
    conditional_stats,
    baseline_stats,
    align_close,
    relative_strength,
    rebased_performance,
    rs_state,
    monthly_returns,
    seasonality_table,
    monthly_summary,
    compute_obv,
    detect_obv_divergence,
    compute_vwap,
    vwap_state,
    compute_acf_pacf,
    compute_return_distribution_stats,
    compute_stationarity_tests,
    cusum_instability_test,
    detect_structural_breaks,
    compute_hurst_analysis,
    compute_quantile_beta,
    compute_regime_conditional_stats,
    ljung_box_test,
    variance_ratio_test,
    distribution_uncertainty,
    compute_52week_range,
    compute_drawdown_series,
    find_drawdown_episodes,
    compute_liquidity_metrics,
    compute_beta,
    compute_stochastic,
    stochastic_state,
    compute_mfi,
    mfi_state,
    compute_avwap,
)
from techna.scoring import compute_dimension_scores
from techna.briefing import build_analyst_briefing
from techna.report_builder import (
    build_report,
    print_terminal_summary,
    trend_finding,
    momentum_finding,
    volatility_finding,
    levels_finding,
    context_finding,
    relative_finding,
    seasonality_finding,
    volume_finding,
    econometrics_finding,
    risk_finding,
    scores_finding,
    render_report_notebook,
    mtf_finding,
    events_finding,
    volume_profile_finding,
    squeeze_finding,
    volume_profile_weekly_finding,
    fibonacci_finding,
    donchian_finding,
    candles_finding,
)


def run(
    ticker: str,
    *,
    interval: str = config.DEFAULT_INTERVAL,
    force_refresh: bool = False,
    no_interactive: bool = False,
    no_chart: bool = False,
    out_dir: Optional[str] = None,
    console: Optional[Console] = None,
    benchmark_ticker: str = config.DEFAULT_BENCHMARK,
    explain: bool = False,
    period: Optional[str] = None,
    notebook: bool = True,
) -> int:
    """Fetch prices, compute indicators, print summary, and build markdown/chart reports.
    
    Returns:
        int: Process exit code (0 for success, 1 for runtime/data errors).
    """
    console = console or Console()
    
    # 1. Fetch prices
    try:
        data = dl.get_prices(
            ticker, interval=interval, period=period, force_refresh=force_refresh, min_rows=1
        )
    except dl.InvalidTickerError as exc:
        console.print(Panel(str(exc), title="Techna — invalid ticker error", border_style="red"))
        return 1
    except dl.InsufficientDataError as exc:
        console.print(Panel(str(exc), title="Techna — insufficient data error", border_style="red"))
        return 1
    except dl.NetworkError as exc:
        console.print(Panel(str(exc), title="Techna — network error", border_style="red"))
        return 1
    except dl.DataLayerError as exc:
        console.print(Panel(str(exc), title="Techna — data layer error", border_style="red"))
        return 1

    df = data.df
    prices = df["Close"]

    # Data provenance — always visible, so an automated/daily run can never
    # silently analyze a stale snapshot without the operator seeing it.
    # ASCII only: fancy arrows crash on legacy Windows console codepages (cp1254).
    console.print(
        f"Data: {data.source} | {len(df)} bars | "
        f"{df.index.min().date()} to {df.index.max().date()}"
    )

    # Same facts, structured for the JSON sidecar / markdown / notebook -- one
    # dict, three consumers, so "what was this run's input?" never has to be
    # reverse-engineered from scattered code. Every number every module
    # computes below is a function of exactly this input.
    data_provenance = {
        "source": data.source,
        "interval": interval,
        "period_requested": period or config.DEFAULT_PERIOD,
        "n_bars": len(df),
        "first_bar_date": str(df.index.min().date()),
        "last_bar_date": str(df.index.max().date()),
        "benchmark_ticker": benchmark_ticker,
    }

    # Accumulate module warning list
    all_warnings = list(data.warnings)
    
    if len(df) < config.TAIL_MIN_OBS:
        msg = f"History is short (n={len(df)}); tail statistics (kurtosis) are unreliable - consider --period 5y"
        all_warnings.append(msg)

    # 2. Compute Indicators
    
    # Category A: Trend Indicators (SMA, EMA, Crossover, Trend State)
    vp_dict = None
    vpw_dict = None
    squeeze_dict = None
    fib_dict = None
    donchian_dict = None
    candles_dict: dict[str, Any] | None = None
    trend_warnings = []
    trend_status = "ok"
    sma50 = None
    sma200 = None
    sma20 = compute_sma(prices, config.SMA_FAST) if len(df) >= config.SMA_FAST else None
    t_state = "sideways"
    last_cross = ("none", "N/A")
    cross_df = None

    if len(df) >= config.SMA_SLOW:
        sma50 = compute_sma(prices, config.SMA_MID)
        sma200 = compute_sma(prices, config.SMA_SLOW)
        cross_df = detect_cross(sma50, sma200)
        t_state = trend_state(prices, sma50, sma200)

        # Last cross event
        crosses = cross_df[cross_df["cross"] != "none"]
        if not crosses.empty:
            last_cross_type = crosses["cross"].iloc[-1]
            last_cross_date = str(crosses.index[-1].date())
            last_cross = (last_cross_type, last_cross_date)
    else:
        trend_status = "warning"
        msg = f"Insufficient history ({len(df)} bars) for SMA{config.SMA_SLOW}. Trend state/cross detection skipped."
        trend_warnings.append(msg)
        all_warnings.append(msg)
        if len(df) >= config.SMA_MID:
            sma50 = compute_sma(prices, config.SMA_MID)
            
    t_finding_val = trend_finding(t_state, last_cross) if trend_status == "ok" else "Insufficient history to compute this finding."
    trend_metrics = {
        "state": t_state,
        "last_cross": last_cross,
        "finding": t_finding_val,
    }
    trend_res = io_contract.make_result(
        "trend",
        data.ticker,
        status=trend_status,
        metrics=trend_metrics,
        warnings=trend_warnings,
    )

    # Category A.5: Weekly Timeframe MTF Context
    mtf_warnings = []
    mtf_status = "ok"
    mtf_dict = compute_weekly_context(df, t_state)
    if mtf_dict["status"] == "warning":
        mtf_status = "warning"
        msg = mtf_dict["warning"]
        mtf_warnings.append(msg)
        all_warnings.append(msg)

    mtf_finding_val = mtf_finding(
        mtf_dict.get("weekly_trend_state", "sideways"),
        mtf_dict.get("weekly_rsi_state", "neutral"),
        mtf_dict.get("alignment", "mixed")
    ) if mtf_status == "ok" else "Insufficient history to compute this finding."

    mtf_metrics = {
        "weekly_bars": mtf_dict.get("weekly_bars", 0),
        "weekly_trend_state": mtf_dict.get("weekly_trend_state", "sideways"),
        "weekly_rsi": mtf_dict.get("weekly_rsi", float("nan")),
        "weekly_rsi_state": mtf_dict.get("weekly_rsi_state", "neutral"),
        "weekly_macd_state": mtf_dict.get("weekly_macd_state", "bearish"),
        "weekly_adx": mtf_dict.get("weekly_adx", float("nan")),
        "weekly_trend_regime": mtf_dict.get("weekly_trend_regime", "ranging"),
        "alignment": mtf_dict.get("alignment", "mixed"),
        "finding": mtf_finding_val,
    }

    mtf_res = io_contract.make_result(
        "mtf",
        data.ticker,
        status=mtf_status,
        metrics=mtf_metrics,
        warnings=mtf_warnings,
    )
    
    # Category B: Momentum Indicators (RSI, MACD, Stochastic)
    mom_warnings = []
    mom_status = "ok"
    rsi = None
    macd_df = None
    last_rsi_val = float("nan")
    r_state = "neutral"
    m_state = "bearish"
    last_macd_vals = (0.0, 0.0, 0.0)
    
    stoch_df = None
    last_stoch_k = float("nan")
    last_stoch_d = float("nan")
    stoch_state_val = "neutral"
    stoch_crossover = "none"
    
    if len(df) >= config.RSI_PERIOD + 1:
        rsi = compute_rsi(prices, config.RSI_PERIOD)
        last_rsi_val = rsi.iloc[-1]
        r_state = rsi_state(rsi)
    else:
        mom_status = "warning"
        msg = f"Insufficient history ({len(df)} bars) for RSI({config.RSI_PERIOD}) (needs >={config.RSI_PERIOD + 1})."
        mom_warnings.append(msg)
        all_warnings.append(msg)

    if len(df) >= config.MACD_SLOW:
        macd_df = compute_macd(prices, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL)
        m_state = macd_state(macd_df["hist"])
        last_macd_vals = (
            float(macd_df["macd"].iloc[-1]),
            float(macd_df["signal"].iloc[-1]),
            float(macd_df["hist"].iloc[-1]),
        )
    else:
        mom_status = "warning"
        msg = f"Insufficient history ({len(df)} bars) for MACD({config.MACD_FAST},{config.MACD_SLOW},{config.MACD_SIGNAL}) (needs >={config.MACD_SLOW})."
        mom_warnings.append(msg)
        all_warnings.append(msg)
        
    if len(df) >= 18:
        stoch_df = compute_stochastic(df, k_period=config.STOCH_K, smooth_k=config.STOCH_SMOOTH, d_period=config.STOCH_D)
        last_stoch_k = float(stoch_df["slow_k"].iloc[-1])
        last_stoch_d = float(stoch_df["slow_d"].iloc[-1])
        stoch_state_val = stochastic_state(stoch_df["slow_k"])
        
        # crossover
        prev_k = stoch_df["slow_k"].iloc[-2]
        prev_d = stoch_df["slow_d"].iloc[-2]
        if not pd.isna(prev_k) and not pd.isna(prev_d) and not pd.isna(last_stoch_k) and not pd.isna(last_stoch_d):
            if prev_k < prev_d and last_stoch_k > last_stoch_d:
                stoch_crossover = "golden_kd"
            elif prev_k > prev_d and last_stoch_k < last_stoch_d:
                stoch_crossover = "death_kd"
    else:
        mom_status = "warning"
        msg = f"Insufficient history ({len(df)} bars) for Stochastic(14,3,3) (needs >=18)."
        mom_warnings.append(msg)
        all_warnings.append(msg)

    stoch_status = "ok" if stoch_df is not None else "warning"
    stoch_dict = {
        "status": stoch_status,
        "slow_k": last_stoch_k,
        "slow_d": last_stoch_d,
        "state": stoch_state_val,
        "crossover": stoch_crossover,
        "_slow_k_series": stoch_df["slow_k"] if stoch_df is not None else pd.Series(dtype=float),
    }

    m_h = last_macd_vals[2] if last_macd_vals is not None else 0.0
    m_finding_val = momentum_finding(
        r_state,
        m_state,
        last_rsi_val,
        m_h,
        stoch_state_val,
        last_stoch_k,
    ) if (r_state is not None and m_state is not None and last_rsi_val is not None) else "Insufficient history to compute this finding."
    
    mom_metrics = {
        "last_rsi": last_rsi_val,
        "rsi_state": r_state,
        "macd_state": m_state,
        "last_macd": last_macd_vals,
        "last_stoch_k": last_stoch_k,
        "last_stoch_d": last_stoch_d,
        "stoch_state": stoch_state_val,
        "stoch_crossover": stoch_crossover,
        "finding": m_finding_val,
    }
    mom_res = io_contract.make_result(
        "momentum",
        data.ticker,
        status=mom_status,
        metrics=mom_metrics,
        warnings=mom_warnings,
    )
    
    # Category C: Volatility (Bollinger Bands)
    vol_warnings = []
    vol_status = "ok"
    boll_df = None
    b_state = "within_bands"
    last_bands = (0.0, 0.0, 0.0, 0.0, 0.0)
    
    if len(df) >= config.BOLLINGER_WINDOW:
        boll_df = compute_bollinger(prices, config.BOLLINGER_WINDOW, config.BOLLINGER_STD)
        b_state = bollinger_state(prices, boll_df["upper"], boll_df["mid"], boll_df["lower"])
        last_row = boll_df.iloc[-1]
        last_bands = (
            float(last_row["mid"]),
            float(last_row["upper"]),
            float(last_row["lower"]),
            float(last_row["pct_b"]),
            float(last_row["bandwidth"]),
        )
    else:
        vol_status = "warning"
        msg = f"Insufficient history ({len(df)} bars) for Bollinger Bands({config.BOLLINGER_WINDOW}) (needs >={config.BOLLINGER_WINDOW})."
        vol_warnings.append(msg)
        all_warnings.append(msg)
        
    v_pct_b = last_bands[3] if last_bands is not None else float('nan')
    v_upper = last_bands[1] if last_bands is not None else float('nan')
    v_lower = last_bands[2] if last_bands is not None else float('nan')
    v_finding_val = volatility_finding(
        b_state,
        v_pct_b,
        v_upper,
        v_lower
    ) if vol_status == "ok" else "Insufficient history to compute this finding."
    
    vol_metrics = {
        "state": b_state,
        "last_bands": last_bands,
        "finding": v_finding_val,
    }
    vol_res = io_contract.make_result(
        "volatility",
        data.ticker,
        status=vol_status,
        metrics=vol_metrics,
        warnings=vol_warnings,
    )
    
    # Category C.5: Volatility Squeeze (Bollinger Squeeze vs Keltner Channels)
    squeeze_warnings = []
    squeeze_status = "ok"
    squeeze_dict = None

    try:
        squeeze_dict = compute_squeeze(
            df,
            # Same window as the main Bollinger Bands module -- the squeeze
            # convention compares THIS ticker's own BB against Keltner using
            # one shared period, not an independently-set duplicate.
            period=config.BOLLINGER_WINDOW,
            bb_mult=config.BOLLINGER_STD,
            kc_mult=config.KC_MULT,
        )
        if squeeze_dict.get("status") == "warning":
            squeeze_status = "warning"
            squeeze_warnings.append(squeeze_dict["warning"])
    except Exception as exc:
        squeeze_status = "warning"
        msg = f"Failed to compute volatility squeeze: {exc}"
        squeeze_warnings.append(msg)
        all_warnings.append(msg)

    sq_finding_val = squeeze_finding(
        squeeze_dict["squeeze_active"] if squeeze_dict is not None else False,
        squeeze_dict["squeeze_duration"] if squeeze_dict is not None else 0,
    ) if squeeze_dict is not None and squeeze_dict.get("status") == "ok" else "Insufficient history to compute this finding."

    squeeze_res = io_contract.make_result(
        "squeeze",
        data.ticker,
        status=squeeze_status,
        metrics={
            "squeeze_active": squeeze_dict["squeeze_active"] if squeeze_dict is not None else False,
            "squeeze_value": float(squeeze_dict["squeeze_value"]) if squeeze_dict is not None else float("nan"),
            "squeeze_duration": int(squeeze_dict["squeeze_duration"]) if squeeze_dict is not None else 0,
            "finding": sq_finding_val,
        },
        warnings=squeeze_warnings,
    )

    # Category D: Levels (Support/Resistance Pivots)
    lev_warnings = []
    lev_status = "ok"
    lev_df = None
    pivots_dict: dict[str, Any] = {"supports": [], "resistances": []}
    v2_levels: dict[str, Any] = {"supports": [], "resistances": []}
    
    if len(df) >= 2 * config.SWING_WINDOW + 1:
        lev_df = find_support_resistance(prices, k=config.SWING_WINDOW)
        tolerance = float(prices.iloc[-1]) * config.LEVEL_CLUSTER_PCT
        v2_levels = select_levels(
            prices,
            k=config.SWING_WINDOW,
            tolerance=tolerance,
            top_n=config.LEVEL_TOP_N,
        )
        pivots_dict = {
            "supports": [float(x["price"]) for x in v2_levels["supports"]],
            "resistances": [float(x["price"]) for x in v2_levels["resistances"]],
        }
    else:
        lev_status = "warning"
        msg = f"Insufficient history ({len(df)} bars) for pivot levels (needs >={2 * config.SWING_WINDOW + 1})."
        lev_warnings.append(msg)
        all_warnings.append(msg)
        
    supports_lst = pivots_dict.get("supports", []) if pivots_dict else []
    resistances_lst = pivots_dict.get("resistances", []) if pivots_dict else []
    l_finding_val = levels_finding(supports_lst, resistances_lst) if lev_status == "ok" else "Insufficient history to compute this finding."
    
    lev_metrics = {
        "pivots": pivots_dict,
        "v2_levels": v2_levels,
        "finding": l_finding_val,
    }
    lev_res = io_contract.make_result(
        "levels",
        data.ticker,
        status=lev_status,
        metrics=lev_metrics,
        warnings=lev_warnings,
    )

    # Category E: Context & Regime (ATR volatility, ADX trend strength, divergence)
    # This layer describes the regime so the indicators above are not read naively.
    ctx_warnings = []
    ctx_status = "ok"
    trend_reg = "undetermined"
    vol_reg = "unknown"
    last_atr = float("nan")
    last_adx = float("nan")
    atr_series = None
    adx_df = None
    divergence: dict[str, Any] = {"bearish": False, "bullish": False, "detail": None}

    atr_min = config.ATR_PERIOD + 1
    adx_min = 2 * config.ADX_PERIOD + 1
    if len(df) >= atr_min:
        atr_series = compute_atr(df, config.ATR_PERIOD)
        last_atr = float(atr_series.iloc[-1])
        vol_reg = volatility_regime(atr_series, df["Close"])
    else:
        ctx_status = "warning"
        msg = f"Insufficient history ({len(df)} bars) for ATR({config.ATR_PERIOD})."
        ctx_warnings.append(msg)
        all_warnings.append(msg)

    if len(df) >= adx_min:
        adx_df = compute_adx(df, config.ADX_PERIOD)
        last_adx = float(adx_df["adx"].iloc[-1])
        trend_reg = trend_regime(adx_df["adx"], adx_df["plus_di"], adx_df["minus_di"])
    else:
        ctx_status = "warning"
        msg = f"Insufficient history ({len(df)} bars) for ADX (needs >={adx_min})."
        ctx_warnings.append(msg)
        all_warnings.append(msg)

    # Divergence between price and RSI (only if RSI was computed above).
    if rsi is not None and rsi.notna().sum() >= 2 * config.SWING_WINDOW + 2:
        divergence = detect_divergence(prices, rsi)

    ctx_finding_val = context_finding(
        trend_reg,
        last_adx,
        vol_reg,
        last_atr,
        divergence.get("detail", "")
    ) if ctx_status == "ok" else "Insufficient history to compute this finding."
    
    ctx_metrics = {
        "trend_regime": trend_reg,
        "volatility_regime": vol_reg,
        "last_atr": last_atr,
        "last_adx": last_adx,
        "divergence": divergence,
        "finding": ctx_finding_val,
    }
    ctx_res = io_contract.make_result(
        "context",
        data.ticker,
        status=ctx_status,
        metrics=ctx_metrics,
        warnings=ctx_warnings,
    )

    # Calculate base rates stats and series
    baserates_stats = []
    fwd10 = None
    cond_rsi = pd.Series(False, index=prices.index)
    cond_boll = pd.Series(False, index=prices.index)
    cond_stoch = pd.Series(False, index=prices.index)
    cond_donchian_55 = pd.Series(False, index=prices.index)
    cond_bull_eng = pd.Series(False, index=prices.index)
    
    if len(prices) >= 5:
        # rsi/boll_df may be None when history is too short for those indicators;
        # fall back to an all-False condition rather than crashing.
        cond_rsi = (
            rsi >= config.RSI_OVERBOUGHT
            if rsi is not None
            else pd.Series(False, index=prices.index)
        )
        cond_boll = (
            prices > boll_df["upper"]
            if boll_df is not None
            else pd.Series(False, index=prices.index)
        )
        cond_stoch = (
            stoch_df["slow_k"] >= config.STOCH_OVERBOUGHT
            if stoch_df is not None
            else pd.Series(False, index=prices.index)
        )
        if len(df) >= 56:
            upper_55_series = df["High"].rolling(window=55).max()
            cond_donchian_55 = prices > upper_55_series.shift(1)
            
        if len(df) >= 3:
            o_ser = df["Open"]
            c_ser = df["Close"]
            body_ser = (c_ser - o_ser).abs()
            prev_close = c_ser.shift(1)
            prev_open = o_ser.shift(1)
            prev_body = body_ser.shift(1)
            prev_bearish = prev_close < prev_open
            curr_bullish = c_ser > o_ser
            engulfs_bullish = (o_ser <= prev_close) & (c_ser > prev_open) & (body_ser > prev_body)
            cond_bull_eng = prev_bearish & curr_bullish & engulfs_bullish

        for h in config.BASE_RATE_HORIZONS:
            if len(prices) > h:
                fwd_h = forward_return(prices, h)
                if h == 10:
                    fwd10 = fwd_h
                
                base_s = baseline_stats(fwd_h)
                base_s.update({"horizon": h, "condition": "Baseline"})
                baserates_stats.append(base_s)
                
                rsi_s = conditional_stats(cond_rsi, fwd_h, min_sample=config.BASE_RATE_MIN_SAMPLE)
                rsi_s.update({"horizon": h, "condition": f"RSI >= {config.RSI_OVERBOUGHT:.0f}"})
                baserates_stats.append(rsi_s)

                boll_s = conditional_stats(cond_boll, fwd_h, min_sample=config.BASE_RATE_MIN_SAMPLE)
                boll_s.update({"horizon": h, "condition": "Close > Bollinger Upper"})
                baserates_stats.append(boll_s)

                stoch_s = conditional_stats(cond_stoch, fwd_h, min_sample=config.BASE_RATE_MIN_SAMPLE)
                stoch_s.update({"horizon": h, "condition": f"Stochastic >= {config.STOCH_OVERBOUGHT:.0f}"})
                baserates_stats.append(stoch_s)
                
                don55_s = conditional_stats(cond_donchian_55, fwd_h, min_sample=config.BASE_RATE_MIN_SAMPLE)
                don55_s.update({"horizon": h, "condition": "Donchian 55 Break High"})
                baserates_stats.append(don55_s)
                
                bull_eng_s = conditional_stats(cond_bull_eng, fwd_h, min_sample=config.BASE_RATE_MIN_SAMPLE)
                bull_eng_s.update({"horizon": h, "condition": "Bullish Engulfing"})
                baserates_stats.append(bull_eng_s)

    # Category F: Relative Strength (Benchmark)
    rel_warnings = []
    rel_status = "ok"
    rel_dict = None
    aligned_asset = None
    aligned_bench = None
    
    try:
        bench_data = dl.get_prices(
            benchmark_ticker,
            interval=interval,
            period=period,
            force_refresh=force_refresh,
            min_rows=1
        )
        aligned_asset, aligned_bench = align_close(prices, bench_data.df["Close"])
        if len(aligned_asset) >= 2:
            rs = relative_strength(aligned_asset, aligned_bench)
            rs_ma = compute_sma(rs, config.RS_MA_WINDOW)
            rel_state_val = rs_state(rs, rs_ma)
            
            asset_rebased = rebased_performance(aligned_asset)
            bench_rebased = rebased_performance(aligned_bench)
            
            rel_dict = {
                "benchmark_ticker": benchmark_ticker,
                "asset_rebased": asset_rebased,
                "bench_rebased": bench_rebased,
                "rs": rs,
                "rs_ma": rs_ma,
                "state": rel_state_val,
            }
        else:
            rel_status = "warning"
            msg = f"Insufficient overlapping history between {ticker} and benchmark {benchmark_ticker}."
            rel_warnings.append(msg)
            all_warnings.append(msg)
    except dl.DataLayerError as exc:
        rel_status = "warning"
        msg = f"Failed to fetch benchmark ticker {benchmark_ticker}: {exc}. Skipping relative strength analysis."
        rel_warnings.append(msg)
        all_warnings.append(msg)

    rel_finding_val = relative_finding(
        benchmark_ticker,
        rel_dict["state"] if rel_dict is not None else "neutral",
        float(rel_dict["rs"].iloc[-1]) if rel_dict is not None else float("nan"),
        float(rel_dict["rs_ma"].iloc[-1]) if rel_dict is not None else float("nan")
    ) if rel_status == "ok" else "Insufficient history to compute this finding."

    rel_res = io_contract.make_result(
        "relative",
        data.ticker,
        status=rel_status,
        metrics={
            "state": rel_dict["state"] if rel_dict is not None else "neutral",
            "benchmark_ticker": benchmark_ticker,
            "last_rs": float(rel_dict["rs"].iloc[-1]) if rel_dict is not None else float("nan"),
            "last_rs_ma": float(rel_dict["rs_ma"].iloc[-1]) if rel_dict is not None else float("nan"),
            "finding": rel_finding_val,
        },
        warnings=rel_warnings,
    )

    # Category G: Seasonality
    seas_warnings = []
    seas_status = "ok"
    seas_table = None
    seas_summary = None
    
    if len(df) >= 2 and (df.index.max() - df.index.min()).days >= 365:
        try:
            m_ret = monthly_returns(prices)
            seas_table = seasonality_table(m_ret)
            seas_summary = monthly_summary(m_ret)
        except Exception as exc:
            seas_status = "warning"
            msg = f"Failed to compute seasonality: {exc}"
            seas_warnings.append(msg)
            all_warnings.append(msg)
    else:
        seas_status = "warning"
        msg = f"Insufficient history ({len(df)} bars) for seasonality analysis (needs >= 1 year)."
        seas_warnings.append(msg)
        all_warnings.append(msg)
        
    best_month_name = "N/A"
    best_month_ret = float('nan')
    best_month_wr = float('nan')
    col_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    if seas_summary is not None and not seas_summary.empty:
        valid_seas = seas_summary.dropna(subset=["mean"])
        if not valid_seas.empty:
            best_idx = valid_seas["mean"].idxmax()
            best_row = valid_seas.loc[best_idx]
            best_month_name = col_names[best_idx - 1]
            best_month_ret = float(best_row["mean"])
            best_month_wr = float(best_row["win_rate"])
            
    seas_finding_val = seasonality_finding(best_month_name, best_month_ret, best_month_wr) if seas_status == "ok" else "Insufficient history to compute this finding."

    seas_res = io_contract.make_result(
        "seasonality",
        data.ticker,
        status=seas_status,
        metrics={
            "has_seasonality": seas_table is not None,
            "best_month": best_month_name,
            "best_month_avg_return": best_month_ret,
            "best_month_win_rate": best_month_wr,
            "finding": seas_finding_val,
        },
        warnings=seas_warnings,
    )

    # Category H: Volume Analysis
    vol_warnings = []
    vol_status = "ok"
    vol_dict = None
    vwap = None
    
    if len(df) >= 2:
        try:
            vwap = compute_vwap(df["High"], df["Low"], df["Close"], df["Volume"], period=config.VWAP_DEFAULT_PERIOD)
            obv = compute_obv(df["Close"], df["Volume"])
            obv_div = detect_obv_divergence(df["Close"], obv, lookback=config.OBV_DIVERGENCE_LOOKBACK)
            v_state = vwap_state(df["Close"], vwap)
            
            # MFI
            mfi_series = pd.Series(dtype=float)
            last_mfi = float("nan")
            mfi_lbl = "neutral"
            if len(df) >= config.MFI_PERIOD + 1:
                mfi_series = compute_mfi(df, period=config.MFI_PERIOD)
                last_mfi = float(mfi_series.iloc[-1])
                mfi_lbl = mfi_state(mfi_series)
                
            # Anchored VWAP (YTD, 52w High, 52w Low)
            avwap_ytd = pd.Series(dtype=float)
            avwap_high = pd.Series(dtype=float)
            avwap_low = pd.Series(dtype=float)
            
            ytd_val, high_val, low_val = float("nan"), float("nan"), float("nan")
            ytd_state, high_state, low_state = "unknown", "unknown", "unknown"
            
            current_year = df.index[-1].year
            ytd_mask = df.index.year == current_year
            ytd_indices = np.where(ytd_mask)[0]
            
            ytd_anchor = ytd_indices[0] if len(ytd_indices) > 0 else -1
            if ytd_anchor >= 0:
                avwap_ytd = compute_avwap(df, ytd_anchor)
                
            # Same window as the 52-week range module (config.WEEK52_WINDOW) --
            # both describe "this ticker's 52-week high/low"; they must anchor
            # on the identical window, not an independently hardcoded one.
            w52 = config.WEEK52_WINDOW
            sub_high = df["High"].iloc[-w52:] if len(df) >= w52 else df["High"]
            high_anchor_date = sub_high.idxmax()
            high_anchor = np.where(df.index == high_anchor_date)[0][0]
            avwap_high = compute_avwap(df, high_anchor)

            sub_low = df["Low"].iloc[-w52:] if len(df) >= w52 else df["Low"]
            low_anchor_date = sub_low.idxmin()
            low_anchor = np.where(df.index == low_anchor_date)[0][0]
            avwap_low = compute_avwap(df, low_anchor)
            
            close_last = float(df["Close"].iloc[-1])
            if not avwap_ytd.empty and not pd.isna(avwap_ytd.iloc[-1]):
                ytd_val = float(avwap_ytd.iloc[-1])
                ytd_state = "above" if close_last > ytd_val else "below"
            if not avwap_high.empty and not pd.isna(avwap_high.iloc[-1]):
                high_val = float(avwap_high.iloc[-1])
                high_state = "above" if close_last > high_val else "below"
            if not avwap_low.empty and not pd.isna(avwap_low.iloc[-1]):
                low_val = float(avwap_low.iloc[-1])
                low_state = "above" if close_last > low_val else "below"
                
            avwap_dict = {
                "ytd_val": ytd_val,
                "ytd_state": ytd_state,
                "high_val": high_val,
                "high_state": high_state,
                "low_val": low_val,
                "low_state": low_state,
                "_ytd_series": avwap_ytd,
                "_high_series": avwap_high,
                "_low_series": avwap_low,
            }
            
            vol_dict = {
                "vwap": vwap,
                "obv": obv,
                "divergence": obv_div,
                "state": v_state,
                "mfi_value": last_mfi,
                "mfi_state": mfi_lbl,
                "_mfi_series": mfi_series,
                "anchored_vwap": avwap_dict,
            }
        except Exception as exc:
            vol_status = "warning"
            msg = f"Failed to compute volume indicators: {exc}"
            vol_warnings.append(msg)
            all_warnings.append(msg)
    else:
        vol_status = "warning"
        msg = f"Insufficient history ({len(df)} bars) for volume analysis."
        vol_warnings.append(msg)
        all_warnings.append(msg)
        
    v_finding_val = volume_finding(
        vol_dict["divergence"]["state"] if vol_dict is not None else "unknown",
        float(vol_dict["divergence"]["price_slope"]) if vol_dict is not None else float("nan"),
        float(vol_dict["divergence"]["obv_slope"]) if vol_dict is not None else float("nan"),
        vol_dict["state"]["state"] if vol_dict is not None else "unknown",
        float(vol_dict["state"]["distance_pct"]) if vol_dict is not None else float("nan"),
        vol_dict.get("mfi_value") if vol_dict is not None else float("nan"),
        vol_dict.get("mfi_state") if vol_dict is not None else "neutral",
        vol_dict.get("anchored_vwap", {}).get("ytd_state") if vol_dict is not None else "unknown",
        vol_dict.get("anchored_vwap", {}).get("high_state") if vol_dict is not None else "unknown",
        vol_dict.get("anchored_vwap", {}).get("low_state") if vol_dict is not None else "unknown",
    ) if vol_status == "ok" else "Insufficient history to compute this finding."

    volume_res = io_contract.make_result(
        "volume",
        data.ticker,
        status=vol_status,
        metrics={
            "state": vol_dict["state"]["state"] if vol_dict is not None else "unknown",
            "divergence_state": vol_dict["divergence"]["state"] if vol_dict is not None else "unknown",
            "price_slope": float(vol_dict["divergence"]["price_slope"]) if vol_dict is not None else float("nan"),
            "obv_slope": float(vol_dict["divergence"]["obv_slope"]) if vol_dict is not None else float("nan"),
            "vwap_distance_pct": float(vol_dict["state"]["distance_pct"]) if vol_dict is not None else float("nan"),
            "mfi_value": float(vol_dict["mfi_value"]) if (vol_dict is not None and "mfi_value" in vol_dict) else float("nan"),
            "mfi_state": vol_dict["mfi_state"] if (vol_dict is not None and "mfi_state" in vol_dict) else "neutral",
            "anchored_vwap": vol_dict["anchored_vwap"] if (vol_dict is not None and "anchored_vwap" in vol_dict) else {},
            "finding": v_finding_val,
        },
        warnings=vol_warnings,
    )

    # Category H.5: Volume Profile Analysis
    vp_warnings = []
    vp_status = "ok"
    vp_dict = None

    try:
        vp_dict = compute_volume_profile(
            df,
            lookback=config.VP_LOOKBACK,
            bins=config.VP_BINS,
            value_area_pct=config.VP_VALUE_AREA,
        )
        if vp_dict.get("status") == "warning":
            vp_status = "warning"
            vp_warnings.append(vp_dict["warning"])
    except Exception as exc:
        vp_status = "warning"
        msg = f"Failed to compute volume profile: {exc}"
        vp_warnings.append(msg)
        all_warnings.append(msg)

    vp_finding_val = volume_profile_finding(
        vp_dict["state"] if vp_dict is not None else "unknown",
        float(vp_dict["poc"]) if vp_dict is not None else float("nan"),
        float(vp_dict["vah"]) if vp_dict is not None else float("nan"),
        float(vp_dict["val"]) if vp_dict is not None else float("nan"),
    ) if vp_dict is not None and vp_dict.get("status") == "ok" else "Insufficient history to compute this finding."

    vp_res = io_contract.make_result(
        "volume_profile",
        data.ticker,
        status=vp_status,
        metrics={
            "poc": float(vp_dict["poc"]) if vp_dict is not None else float("nan"),
            "vah": float(vp_dict["vah"]) if vp_dict is not None else float("nan"),
            "val": float(vp_dict["val"]) if vp_dict is not None else float("nan"),
            "state": vp_dict["state"] if vp_dict is not None else "unknown",
            "lookback_used": int(vp_dict["lookback_used"]) if vp_dict is not None else 0,
            "finding": vp_finding_val,
        },
        warnings=vp_warnings,
    )

    # Category H.6: Weekly Volume Profile Analysis
    vpw_warnings = []
    vpw_status = "ok"
    vpw_dict = None

    try:
        vpw_dict = compute_volume_profile_weekly(
            df,
            lookback_weeks=config.VP_WEEKLY_LOOKBACK_WEEKS,
            bins=config.VP_BINS,
            value_area=config.VP_VALUE_AREA,
        )
        if vpw_dict.get("status") == "warning":
            vpw_status = "warning"
            vpw_warnings.append(vpw_dict["warning"])
    except Exception as exc:
        vpw_status = "warning"
        msg = f"Failed to compute weekly volume profile: {exc}"
        vpw_warnings.append(msg)
        all_warnings.append(msg)

    vpw_finding_val = volume_profile_weekly_finding(
        vpw_dict["state_weekly"] if vpw_dict is not None else "unknown",
        float(vpw_dict["poc_weekly"]) if vpw_dict is not None else float("nan"),
        float(vpw_dict["vah_weekly"]) if vpw_dict is not None else float("nan"),
        float(vpw_dict["val_weekly"]) if vpw_dict is not None else float("nan"),
    ) if vpw_dict is not None and vpw_dict.get("status") == "ok" else "Insufficient history to compute this finding."

    vpw_res = io_contract.make_result(
        "volume_profile_weekly",
        data.ticker,
        status=vpw_status,
        metrics={
            "poc_weekly": float(vpw_dict["poc_weekly"]) if vpw_dict is not None else float("nan"),
            "vah_weekly": float(vpw_dict["vah_weekly"]) if vpw_dict is not None else float("nan"),
            "val_weekly": float(vpw_dict["val_weekly"]) if vpw_dict is not None else float("nan"),
            "state_weekly": vpw_dict["state_weekly"] if vpw_dict is not None else "unknown",
            "weeks_used": int(vpw_dict["weeks_used"]) if vpw_dict is not None else 0,
            "finding": vpw_finding_val,
        },
        warnings=vpw_warnings,
    )

    # Category H.7: Fibonacci Retracement Analysis
    fib_warnings = []
    fib_status = "ok"
    fib_dict = None

    try:
        fib_dict = compute_fibonacci(
            df,
            lookback=config.FIB_LOOKBACK,
            levels=config.FIB_LEVELS,
            touch_atr_mult=config.FIB_TOUCH_ATR_MULT,
        )
        if fib_dict.get("status") == "warning":
            fib_status = "warning"
            fib_warnings.append(fib_dict["warning"])
    except Exception as exc:
        fib_status = "warning"
        msg = f"Failed to compute Fibonacci retracement: {exc}"
        fib_warnings.append(msg)
        all_warnings.append(msg)

    fib_finding_val = fibonacci_finding(
        fib_dict
    ) if fib_dict is not None and fib_dict.get("status") in ("ok", "warning") else "Insufficient history to compute this finding."

    fib_res = io_contract.make_result(
        "fibonacci",
        data.ticker,
        status=fib_status,
        metrics={
            "swing_high": float(fib_dict["swing_high"]) if fib_dict is not None else float("nan"),
            "swing_low": float(fib_dict["swing_low"]) if fib_dict is not None else float("nan"),
            "direction": fib_dict["direction"] if fib_dict is not None else "none",
            "levels": fib_dict["levels"] if fib_dict is not None else {},
            "respect_stats": fib_dict["respect_stats"] if fib_dict is not None else {},
            "current_position": fib_dict["current_position"] if fib_dict is not None else {},
            "finding": fib_finding_val,
        },
        warnings=fib_warnings,
    )

    # Category H.8: Donchian Channels Analysis
    donchian_warnings = []
    donchian_status = "ok"
    donchian_dict = None

    try:
        don_df = compute_donchian(
            df,
            fast=config.DONCHIAN_FAST,
            slow=config.DONCHIAN_SLOW,
        )
        
        last_pos_20 = float(don_df["pos_pct_20"].iloc[-1])
        last_pos_55 = float(don_df["pos_pct_55"].iloc[-1])
        
        # breakout check for finding. The channel series already exclude the
        # current bar (shift(1) inside compute_donchian), so the LAST value of
        # each band is exactly "the prior n-day extreme" -- compare directly.
        breakout_desc = "no breakouts detected today"
        curr_high = df["High"].iloc[-1]
        curr_low = df["Low"].iloc[-1]

        band_upper_20 = don_df["upper_20"].iloc[-1]
        band_lower_20 = don_df["lower_20"].iloc[-1]
        band_upper_55 = don_df["upper_55"].iloc[-1]
        band_lower_55 = don_df["lower_55"].iloc[-1]

        if not pd.isna(band_upper_55) and curr_high > band_upper_55:
            breakout_desc = f"a bullish breakout above the 55-day channel upper band ({band_upper_55:.2f}) occurred today"
        elif not pd.isna(band_lower_55) and curr_low < band_lower_55:
            breakout_desc = f"a bearish breakout below the 55-day channel lower band ({band_lower_55:.2f}) occurred today"
        elif not pd.isna(band_upper_20) and curr_high > band_upper_20:
            breakout_desc = f"a bullish breakout above the 20-day channel upper band ({band_upper_20:.2f}) occurred today"
        elif not pd.isna(band_lower_20) and curr_low < band_lower_20:
            breakout_desc = f"a bearish breakout below the 20-day channel lower band ({band_lower_20:.2f}) occurred today"

        donchian_dict = {
            "status": "ok",
            "upper_20": don_df["upper_20"],
            "lower_20": don_df["lower_20"],
            "mid_20": don_df["mid_20"],
            "pos_pct_20": last_pos_20,
            
            "upper_55": don_df["upper_55"],
            "lower_55": don_df["lower_55"],
            "mid_55": don_df["mid_55"],
            "pos_pct_55": last_pos_55,
            
            "breakout_desc": breakout_desc,
            "_df": don_df,
            "_close_series": df["Close"],
        }
    except Exception as exc:
        donchian_status = "warning"
        msg = f"Failed to compute Donchian Channels: {exc}"
        donchian_warnings.append(msg)
        all_warnings.append(msg)

    don_finding_val = donchian_finding(
        donchian_dict["pos_pct_20"] if donchian_dict is not None else float("nan"),
        donchian_dict["pos_pct_55"] if donchian_dict is not None else float("nan"),
        donchian_dict["breakout_desc"] if donchian_dict is not None else None,
    ) if donchian_dict is not None else "Insufficient history to compute this finding."

    donchian_res = io_contract.make_result(
        "donchian",
        data.ticker,
        status=donchian_status,
        metrics={
            "upper_20": float(donchian_dict["upper_20"].iloc[-1]) if donchian_dict is not None else float("nan"),
            "lower_20": float(donchian_dict["lower_20"].iloc[-1]) if donchian_dict is not None else float("nan"),
            "mid_20": float(donchian_dict["mid_20"].iloc[-1]) if donchian_dict is not None else float("nan"),
            "pos_pct_20": float(donchian_dict["pos_pct_20"]) if donchian_dict is not None else float("nan"),
            
            "upper_55": float(donchian_dict["upper_55"].iloc[-1]) if donchian_dict is not None else float("nan"),
            "lower_55": float(donchian_dict["lower_55"].iloc[-1]) if donchian_dict is not None else float("nan"),
            "mid_55": float(donchian_dict["mid_55"].iloc[-1]) if donchian_dict is not None else float("nan"),
            "pos_pct_55": float(donchian_dict["pos_pct_55"]) if donchian_dict is not None else float("nan"),
            
            "breakout_desc": breakout_desc if donchian_dict is not None else "none",
            "finding": don_finding_val,
        },
        warnings=donchian_warnings,
    )

    # Category H.9: Candlestick Patterns Analysis
    candles_warnings = []
    candles_status = "ok"
    candles_dict = None

    try:
        pat_dict = compute_candle_patterns(df)
        
        candles_dict = {
            "status": "ok",
            "patterns": pat_dict,
        }
    except Exception as exc:
        candles_status = "warning"
        msg = f"Failed to compute candlestick patterns: {exc}"
        candles_warnings.append(msg)
        all_warnings.append(msg)

    candles_finding_val = candles_finding(
        {k: bool(v.iloc[-1]) for k, v in candles_dict["patterns"].items()} if candles_dict is not None else {}
    ) if candles_status == "ok" else "Insufficient history to compute this finding."

    candles_res = io_contract.make_result(
        "candles",
        data.ticker,
        status=candles_status,
        metrics={
            "doji": bool(candles_dict["patterns"]["doji"].iloc[-1]) if candles_dict is not None else False,
            "hammer": bool(candles_dict["patterns"]["hammer"].iloc[-1]) if candles_dict is not None else False,
            "shooting_star": bool(candles_dict["patterns"]["shooting_star"].iloc[-1]) if candles_dict is not None else False,
            "bullish_engulfing": bool(candles_dict["patterns"]["bullish_engulfing"].iloc[-1]) if candles_dict is not None else False,
            "bearish_engulfing": bool(candles_dict["patterns"]["bearish_engulfing"].iloc[-1]) if candles_dict is not None else False,
            "finding": candles_finding_val,
        },
        warnings=candles_warnings,
    )

    # Category I: Econometric Analysis
    econ_warnings = []
    econ_status = "ok"
    econ_dict: dict[str, Any] | None = None
    
    returns = np.log(df["Close"]).diff().dropna()
    
    if len(returns) >= config.ECON_MIN_RETURNS:
        try:
            acf_pacf_res = compute_acf_pacf(returns, lags=config.ACF_LAGS)
            dist_res = compute_return_distribution_stats(returns)
            stationarity_levels = compute_stationarity_tests(df["Close"], regression=config.STATIONARITY_REG_LEVELS)
            stationarity_returns = compute_stationarity_tests(returns, regression=config.STATIONARITY_REG_RETURNS)
            cusum_res = cusum_instability_test(returns)
            breaks_res = detect_structural_breaks(returns)
            hurst_res = compute_hurst_analysis(returns)
            
            regime_cond_res = compute_regime_conditional_stats(returns, breaks_res)
            ljung_box_res = ljung_box_test(returns)
            var_ratio_res = variance_ratio_test(returns)
            dist_unc_res = distribution_uncertainty(returns)
            
            econ_dict = {
                "status": "ok",
                "acf_pacf": acf_pacf_res,
                "distribution": dist_res,
                "stationarity_levels": stationarity_levels,
                "stationarity_returns": stationarity_returns,
                "cusum": cusum_res,
                "breaks": breaks_res,
                "hurst": hurst_res,
                "regime_conditional": regime_cond_res,
                "ljung_box": ljung_box_res,
                "variance_ratio": var_ratio_res,
                "dist_uncertainty": dist_unc_res,
            }
        except Exception as exc:
            econ_status = "warning"
            msg = f"Failed to compute econometric indicators: {exc}"
            econ_warnings.append(msg)
            all_warnings.append(msg)
    else:
        econ_status = "warning"
        msg = f"Insufficient history ({len(returns)} returns) for econometric analysis (needs >= {config.ECON_MIN_RETURNS})."
        econ_warnings.append(msg)
        all_warnings.append(msg)
        
    econ_finding_val = econometrics_finding(
        econ_dict["stationarity_returns"]["state_label"] if econ_dict is not None else "unknown",
        econ_dict["ljung_box"]["significant"] if econ_dict is not None else False,
        len(econ_dict["breaks"]) if econ_dict is not None else 0,
        econ_dict["variance_ratio"]["state_label"] if econ_dict is not None else "unknown"
    ) if econ_status == "ok" else "Insufficient history to compute this finding."

    econ_res = io_contract.make_result(
        "econometrics",
        data.ticker,
        status=econ_status,
        metrics={
            "volatility_clustering_detected": econ_dict["acf_pacf"]["volatility_clustering_detected"] if econ_dict is not None else False,
            "variance_ratio_state": econ_dict["variance_ratio"]["state_label"] if econ_dict is not None else "unknown",
            "ljung_box_significant": econ_dict["ljung_box"]["significant"] if econ_dict is not None else False,
            "regime_conditional_split": econ_dict["regime_conditional"]["is_split"] if econ_dict is not None else False,
            "hurst_returns": econ_dict["hurst"]["returns"]["hurst"] if econ_dict is not None else float("nan"),
            "hurst_volatility": econ_dict["hurst"]["volatility"]["hurst"] if econ_dict is not None else float("nan"),
            "adf_stat": econ_dict["stationarity_returns"]["adf"]["stat"] if econ_dict is not None else float("nan"),
            "adf_pvalue": econ_dict["stationarity_returns"]["adf"]["pvalue"] if econ_dict is not None else float("nan"),
            "kpss_stat": econ_dict["stationarity_returns"]["kpss"]["stat"] if econ_dict is not None else float("nan"),
            "kpss_pvalue": econ_dict["stationarity_returns"]["kpss"]["pvalue"] if econ_dict is not None else float("nan"),
            "skew": econ_dict["distribution"]["skew"] if econ_dict is not None else float("nan"),
            "excess_kurtosis": econ_dict["distribution"]["excess_kurtosis"] if econ_dict is not None else float("nan"),
            "jb_stat": econ_dict["distribution"]["jb_stat"] if econ_dict is not None else float("nan"),
            "jb_pvalue": econ_dict["distribution"]["jb_pvalue"] if econ_dict is not None else float("nan"),
            "finding": econ_finding_val,
        },
        warnings=econ_warnings,
    )

    # Category J: Risk Context
    risk_warnings = []
    risk_status = "ok"
    risk_dict = None
    
    try:
        range_52w = compute_52week_range(df["Close"])
        dd_series = compute_drawdown_series(df["Close"])
        dd_episodes = find_drawdown_episodes(df["Close"], top_n=3)
        liq_metrics = compute_liquidity_metrics(df["Volume"], df["Close"])
        
        beta_metrics = {"beta": float("nan"), "alpha_annualized": float("nan"), "r_squared": float("nan"), "state": "low_beta", "n": 0}
        stock_returns = returns  # reuse the returns already computed at line 494
        bench_returns = pd.Series(dtype=float)
        
        if aligned_asset is not None and aligned_bench is not None:
            aligned_stock_ret = np.log(aligned_asset).diff().dropna()
            aligned_bench_ret = np.log(aligned_bench).diff().dropna()
            
            beta_metrics = compute_beta(aligned_stock_ret, aligned_bench_ret)
            bench_returns = aligned_bench_ret
            stock_returns = aligned_stock_ret
            
        risk_dict = {
            "status": "ok",
            "52week": range_52w,
            "drawdown_series": dd_series,
            "drawdown_episodes": dd_episodes,
            "liquidity": liq_metrics,
            "beta": beta_metrics,
            "stock_returns": stock_returns,
            "bench_returns": bench_returns,
        }
        
        if aligned_asset is not None and aligned_bench is not None and econ_dict is not None:
            try:
                econ_dict["quantile_beta"] = compute_quantile_beta(aligned_stock_ret, aligned_bench_ret)
            except Exception as exc:
                msg = f"Failed to compute quantile regression beta: {exc}"
                econ_warnings.append(msg)
                all_warnings.append(msg)
    except Exception as exc:
        risk_status = "warning"
        msg = f"Failed to compute risk context metrics: {exc}"
        risk_warnings.append(msg)
        all_warnings.append(msg)
        
    risk_finding_val = risk_finding(
        risk_dict["52week"]["state"] if risk_dict is not None else "unknown",
        float(risk_dict["drawdown_series"]["drawdown"].iloc[-1]) * 100.0 if risk_dict is not None else float("nan"),
        risk_dict["liquidity"]["state"] if risk_dict is not None else "unknown",
        float(risk_dict["beta"]["beta"]) if risk_dict is not None else float("nan"),
        risk_dict["beta"]["state"] if risk_dict is not None else "unknown"
    ) if risk_status == "ok" else "Insufficient history to compute this finding."

    risk_res = io_contract.make_result(
        "risk",
        data.ticker,
        status=risk_status,
        metrics={
            "state": risk_dict["52week"]["state"] if risk_dict is not None else "unknown",
            "position_pct_52w": float(risk_dict["52week"]["position_pct"]) if risk_dict is not None else float("nan"),
            "last_drawdown_pct": float(risk_dict["drawdown_series"]["drawdown"].iloc[-1]) * 100.0 if risk_dict is not None else float("nan"),
            "liquidity_state": risk_dict["liquidity"]["state"] if risk_dict is not None else "unknown",
            "avg_value_20": float(risk_dict["liquidity"]["avg_value_20"]) if risk_dict is not None else float("nan"),
            "beta": float(risk_dict["beta"]["beta"]) if risk_dict is not None else float("nan"),
            "beta_state": risk_dict["beta"]["state"] if risk_dict is not None else "unknown",
            "beta_n": int(risk_dict["beta"]["n"]) if risk_dict is not None else 0,
            "finding": risk_finding_val,
        },
        warnings=risk_warnings,
    )

    context_dict = dict(ctx_metrics)
    context_dict["atr"] = atr_series
    context_dict["adx"] = adx_df
    context_dict["baserates_stats"] = baserates_stats
    context_dict["baserates"] = {
        "fwd10": fwd10 if fwd10 is not None else pd.Series(float("nan"), index=prices.index),
        "cond_rsi": cond_rsi,
        "cond_boll": cond_boll,
        "cond_stoch": cond_stoch,
        "cond_donchian_55": cond_donchian_55,
        "cond_bullish_engulfing": cond_bull_eng,
    }
    context_dict["relative"] = rel_dict
    context_dict["seasonality_table"] = seas_table
    context_dict["seasonality_summary"] = seas_summary
    context_dict["volume"] = vol_dict
    context_dict["volume_profile"] = vp_dict
    context_dict["volume_profile_weekly"] = vpw_dict
    context_dict["squeeze"] = squeeze_dict
    context_dict["stochastic"] = stoch_dict
    context_dict["fibonacci"] = fib_dict
    context_dict["donchian"] = donchian_dict
    context_dict["candles"] = candles_dict
    context_dict["econometrics"] = econ_dict
    context_dict["risk"] = risk_dict
    context_dict["mtf"] = mtf_dict
    context_dict["data_provenance"] = data_provenance

    # Category I: Scoring
    scoring_warnings = []
    scoring_status = "ok"
    scores_res = None
    
    try:
        last_adx = float(adx_df["adx"].iloc[-1]) if adx_df is not None and "adx" in adx_df else 15.0
        last_price = float(df["Close"].iloc[-1])
        last_sma200 = float(sma200.iloc[-1]) if sma200 is not None and not sma200.empty else last_price
        last_rsi_val = float(rsi.iloc[-1]) if rsi is not None and not rsi.empty else 50.0
        pos_pct = float(risk_dict["52week"]["position_pct"]) if risk_dict is not None else float("nan")
        liq_avg_val = float(risk_dict["liquidity"]["avg_value_20"]) if risk_dict is not None else 0.0
        
        last_bandwidth = 0.10
        if boll_df is not None and not boll_df.empty:
            up = boll_df["upper"].iloc[-1]
            dn = boll_df["lower"].iloc[-1]
            md = boll_df["mid"].iloc[-1]
            if md != 0:
                last_bandwidth = float((up - dn) / md)
                
        is_rsi_ob = bool(cond_rsi.iloc[-1]) if cond_rsi is not None and not cond_rsi.empty else False
        is_boll_up = bool(cond_boll.iloc[-1]) if cond_boll is not None and not cond_boll.empty else False
        
        scoring_indicators = {
            "adx": last_adx,
            "price": last_price,
            "sma200": last_sma200,
            "last_cross": last_cross[0] if isinstance(last_cross, tuple) else last_cross,
            "rsi": last_rsi_val,
            "macd_state": m_state,
            "position_pct": pos_pct,
            "avg_value_20": liq_avg_val,
            "volatility_regime": vol_reg,
            "bandwidth": last_bandwidth,
            "rsi_overbought": is_rsi_ob,
            "boll_upper": is_boll_up,
            "baserates_stats": baserates_stats,
        }
        scores_res = compute_dimension_scores(scoring_indicators)
    except Exception as exc:
        scoring_status = "warning"
        msg = f"Failed to compute dimension scores: {exc}"
        scoring_warnings.append(msg)
        all_warnings.append(msg)
        
    s_finding_val = scores_finding(
        scores_res["trend_strength"]["value"] if scores_res is not None else 0,
        scores_res["momentum"]["value"] if scores_res is not None else 0,
        scores_res["trend_maturity"]["value"] if scores_res is not None else 0,
        scores_res["liquidity"]["value"] if scores_res is not None else 0,
        scores_res["volatility_level"]["value"] if scores_res is not None else 0,
        scores_res["statistical_edge"]["value"] if scores_res is not None else 0
    ) if scoring_status == "ok" else "Insufficient history to compute this finding."

    scoring_io_res = io_contract.make_result(
        "scores",
        data.ticker,
        status=scoring_status,
        metrics={
            "trend_strength_score": scores_res["trend_strength"]["value"] if scores_res is not None else 0,
            "finding": s_finding_val,
        },
        warnings=scoring_warnings,
    )
    context_dict["scores"] = scores_res

    # Category J: Briefing (Analyst Synthesis Narrative)
    briefing_res = None
    briefing_io_res = None
    if explain:
        briefing_warnings = []
        briefing_status = "ok"
        try:
            if scores_res is not None:
                briefing_res = build_analyst_briefing(scoring_indicators, scores_res)
            else:
                briefing_status = "warning"
                briefing_warnings.append("Briefing calculation skipped due to missing scores.")
        except Exception as exc:
            briefing_status = "warning"
            msg = f"Failed to build analyst briefing: {exc}"
            briefing_warnings.append(msg)
            all_warnings.append(msg)
            
        briefing_io_res = io_contract.make_result(
            "briefing",
            data.ticker,
            status=briefing_status,
            metrics={
                "briefing_len": len(briefing_res) if briefing_res is not None else 0,
                "finding": "Synthesis narrative explaining multi-dimensional technical relationships." if briefing_status == "ok" else "Insufficient history to compute this finding.",
            },
            warnings=briefing_warnings,
        )
    context_dict["briefing"] = briefing_res

    # Category K: Today's Events Detection
    context_dict["df"] = df
    context_dict["rsi"] = rsi
    context_dict["macd"] = macd_df
    context_dict["bollinger"] = boll_df
    context_dict["cross_df"] = cross_df
    context_dict["vwap"] = vwap

    detected_events = compute_events(context_dict)
    context_dict["events"] = detected_events

    events_warnings: list[str] = []
    events_status = "ok"
    events_finding_val = events_finding(detected_events)

    events_metrics = {
        "count": len(detected_events),
        "events": detected_events,
        "finding": events_finding_val,
    }

    events_res = io_contract.make_result(
        "events",
        data.ticker,
        status=events_status,
        metrics=events_metrics,
        warnings=events_warnings,
    )

    # 3. Print terminal Rich summary
    print_terminal_summary(
        data.ticker,
        data,
        trend_metrics,
        mom_metrics,
        vol_metrics,
        lev_metrics,
        context_data=context_dict,
        console=console,
    )
    if all_warnings:
        console.print("[yellow]Warnings:[/yellow] " + "; ".join(all_warnings))
    console.print("[dim]Reminder: Techna reports signal states, never buy/sell advice.[/dim]")
    
    # 4. Generate markdown and chart files
    trend_dict = {
        "state": t_state,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "last_cross": last_cross,
        "candle_patterns": candles_dict["patterns"] if candles_dict is not None else None,
    }
    momentum_dict = {
        "last_rsi": last_rsi_val,
        "rsi_state": r_state,
        "macd_state": m_state,
        "last_macd": last_macd_vals,
        "last_stoch_k": last_stoch_k,
        "last_stoch_d": last_stoch_d,
        "stoch_state": stoch_state_val,
        "stoch_crossover": stoch_crossover,
        "rsi": rsi,
        "macd": macd_df,
        "stochastic": stoch_df,
    }
    volatility_dict = {
        "state": b_state,
        "last_bands": last_bands,
        "upper": boll_df["upper"] if boll_df is not None else None,
        "mid": boll_df["mid"] if boll_df is not None else None,
        "lower": boll_df["lower"] if boll_df is not None else None,
    }
    levels_dict = {
        "pivots": pivots_dict,
        "support": lev_df["support"] if lev_df is not None else None,
        "resistance": lev_df["resistance"] if lev_df is not None else None,
        "v2": lev_metrics["v2_levels"],
    }

    report_path = build_report(
        data.ticker,
        data,
        trend_dict,
        momentum_dict,
        volatility_dict,
        levels_dict,
        context_data=context_dict,
        out_dir=out_dir or config.REPORTS_DIR,
        draw_chart=not no_chart,
        no_interactive=no_interactive,
        warnings=all_warnings,
        console=console,
    )
    
    # 5. Write the structured half of the I/O contract: aggregate every module's
    # result dict into a machine-readable JSON sidecar next to the report.
    module_results = [
        events_res, trend_res, mtf_res, mom_res, vol_res, squeeze_res, lev_res, vp_res, vpw_res, fib_res, donchian_res, candles_res, ctx_res, rel_res,
        seas_res, volume_res, econ_res, risk_res, scoring_io_res,
    ]
    if briefing_io_res is not None:
        module_results.append(briefing_io_res)

    result_path = io_contract.write_results_json(
        out_dir or config.REPORTS_DIR,
        data.ticker,
        report_path,
        module_results,
        warnings=all_warnings,
        data_provenance=data_provenance,
    )

    if notebook:
        try:
            notebook_path = render_report_notebook(
                data.ticker,
                Path(result_path),
                Path(out_dir or config.REPORTS_DIR),
                context_data=context_dict,
            )
            console.print(f"[green]Static notebook generated successfully at:[/green] {notebook_path}")
        except ImportError:
            msg = (
                "Notebook generation skipped: nbformat is not installed. "
                "Run 'pip install -r requirements-notebook.txt' to enable it."
            )
            all_warnings.append(msg)
            console.print(f"[yellow]{msg}[/yellow]")
        except Exception as exc:
            msg = f"Notebook generation failed, continuing without it: {exc}"
            all_warnings.append(msg)
            console.print(f"[yellow]{msg}[/yellow]")

    console.print(f"[green]Report and chart generated successfully at:[/green] {report_path}")
    console.print(f"[green]Structured results written to:[/green] {result_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="techna",
        description="Techna — deterministic technical-analysis agent (signals, not advice).",
    )
    parser.add_argument("ticker", help="ticker symbol, e.g. AAPL or THYAO.IS")
    parser.add_argument(
        "--interval", default=config.DEFAULT_INTERVAL, help="bar interval (default: 1d)"
    )
    parser.add_argument(
        "--period", default=None, help="time period to fetch, e.g. 2y, 5y, 10y, max (default: None, falls back to config.DEFAULT_PERIOD)"
    )
    parser.add_argument(
        "--force-refresh", action="store_true", help="ignore cache and re-fetch"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="skip human confirmation gates",
    )
    parser.add_argument(
        "--no-chart",
        action="store_true",
        help="skip generating PNG chart file",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="custom directory to output reports (default: reports/)",
    )
    parser.add_argument(
        "--benchmark",
        default=config.DEFAULT_BENCHMARK,
        help=f"benchmark ticker for relative strength analysis (default: {config.DEFAULT_BENCHMARK})",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="generate flat-text narrative briefing (Synthesis — Not Advice)",
    )
    parser.add_argument(
        "--notebook",
        dest="notebook",
        action="store_true",
        help="generate the static Jupyter presentation notebook (default: on; kept for backward compatibility)",
    )
    parser.add_argument(
        "--no-notebook",
        dest="notebook",
        action="store_false",
        help="skip generating the static Jupyter presentation notebook",
    )
    parser.set_defaults(notebook=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return run(
        args.ticker,
        interval=args.interval,
        force_refresh=args.force_refresh,
        no_interactive=args.no_interactive,
        no_chart=args.no_chart,
        out_dir=args.out,
        benchmark_ticker=args.benchmark,
        explain=args.explain,
        period=args.period,
        notebook=args.notebook,
    )


if __name__ == "__main__":
    raise SystemExit(main())
