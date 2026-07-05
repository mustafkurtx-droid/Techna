"""Report builder module for Techna.

Generates markdown reports, matplotlib charts (using Agg backend), and Rich console
terminal dashboards.
"""
from __future__ import annotations

from pathlib import Path
import base64
import inspect
import re
import math
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
import scipy.stats

from techna import config
from techna import data_layer as dl
from techna import indicators as ind
from techna.scoring import compute_dimension_scores

# Recent-window size (bars) for the zoomed candlestick chart.
CANDLE_WINDOW = 90


def _save(fig, out_path: Path) -> None:
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def draw_overview_chart(
    ticker: str,
    df: pd.DataFrame,
    trend_data: Dict[str, Any],
    volatility_data: Dict[str, Any],
    levels_data: Dict[str, Any],
    out_path: Path,
) -> None:
    """Price panel (Close, MAs, Bollinger, pivots) over a volume panel."""
    fig, (ax1, ax2) = plt.subplots(
        nrows=2, ncols=1, sharex=True, figsize=(12, 8),
        gridspec_kw={"height_ratios": [3, 1]},
    )

    ax1.plot(df.index, df["Close"], label="Close", color="#1f77b4", linewidth=1.4)
    for key, label, color in (
        ("sma20", "SMA 20", "#9467bd"),
        ("sma50", "SMA 50", "#ff7f0e"),
        ("sma200", "SMA 200", "#d62728"),
    ):
        series = trend_data.get(key)
        if series is not None:
            ax1.plot(df.index, series, label=label, linestyle="--", linewidth=1.0, color=color)

    if volatility_data.get("upper") is not None:
        ax1.plot(df.index, volatility_data["upper"], color="#2ca02c", linestyle=":", alpha=0.7, label="Bollinger")
        ax1.plot(df.index, volatility_data["lower"], color="#2ca02c", linestyle=":", alpha=0.7)
        ax1.fill_between(df.index, volatility_data["lower"], volatility_data["upper"], color="#2ca02c", alpha=0.05)

    # Filtered (v2) support/resistance as horizontal levels — thickness/alpha
    # scaled by strength (touches). Cleaner than scattering every raw pivot.
    v2 = levels_data.get("v2") or {}
    raw_supports = v2.get("supports", [])
    raw_resistances = v2.get("resistances", [])
    current_price = float(df["Close"].iloc[-1])
    
    # Merge levels and combine touches for identical prices
    combined_levels: dict[float, dict[str, Any]] = {}
    for lvl in raw_supports + raw_resistances:
        price = lvl["price"]
        touches = lvl["touches"]
        if price in combined_levels:
            combined_levels[price]["touches"] += touches
        else:
            combined_levels[price] = {"price": price, "touches": touches}
            
    all_levels = list(combined_levels.values())
    supports = [lvl for lvl in all_levels if lvl["price"] <= current_price]
    resistances = [lvl for lvl in all_levels if lvl["price"] > current_price]
    
    # Determine maximum touches to scale alpha and linewidth
    all_touches = [lvl["touches"] for lvl in supports + resistances]
    max_touches = max(all_touches) if all_touches else 1
    sup_labeled = res_labeled = False
    for lvl in supports:
        alpha = 0.25 + 0.45 * (lvl["touches"] / max_touches)
        ax1.axhline(lvl["price"], color="green", linestyle="--", linewidth=1.0, alpha=alpha,
                    label=("Support (filtered)" if not sup_labeled else ""))
        sup_labeled = True
    for lvl in resistances:
        alpha = 0.25 + 0.45 * (lvl["touches"] / max_touches)
        ax1.axhline(lvl["price"], color="red", linestyle="--", linewidth=1.0, alpha=alpha,
                    label=("Resistance (filtered)" if not res_labeled else ""))
        res_labeled = True

    ax1.set_title(f"{ticker} — Price Overview")
    ax1.set_ylabel("Price")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, linestyle=":", alpha=0.6)

    # Volume panel, coloured by up/down day.
    colors = np.where(df["Close"].to_numpy() >= df["Open"].to_numpy(), "#2ca02c", "#d62728")
    ax2.bar(df.index, df["Volume"], color=colors, alpha=0.6, width=1.0)
    ax2.set_ylabel("Volume")
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.set_xlabel("Date")
    _save(fig, out_path)


def draw_momentum_chart(
    ticker: str,
    df: pd.DataFrame,
    momentum_data: Dict[str, Any],
    context_data: Dict[str, Any] | None,
    out_path: Path,
) -> None:
    """RSI panel (with zones + divergence note) over a MACD panel."""
    fig, (ax1, ax2, ax3) = plt.subplots(
        nrows=3, ncols=1, sharex=True, figsize=(12, 9),
        gridspec_kw={"height_ratios": [1, 1, 1]},
    )

    rsi_s = momentum_data.get("rsi")
    if rsi_s is not None:
        ax1.plot(df.index, rsi_s, label=f"RSI ({config.RSI_PERIOD})", color="#9467bd", linewidth=1.2)
        ax1.axhspan(config.RSI_OVERBOUGHT, 100, color="red", alpha=0.07)
        ax1.axhspan(0, config.RSI_OVERSOLD, color="green", alpha=0.07)
        ax1.axhline(config.RSI_OVERBOUGHT, color="red", linestyle="--", alpha=0.5, linewidth=0.8)
        ax1.axhline(config.RSI_OVERSOLD, color="green", linestyle="--", alpha=0.5, linewidth=0.8)
        ax1.set_ylim(0, 100)
        ax1.set_ylabel("RSI")
        ax1.legend(loc="upper left", fontsize=8)
        ax1.grid(True, linestyle=":", alpha=0.6)

    # Divergence annotation (honest: only reported when confirmed).
    div = (context_data or {}).get("divergence") or {}
    if div.get("bearish") or div.get("bullish"):
        kind = "Bearish" if div.get("bearish") else "Bullish"
        ax1.set_title(f"{ticker} — Momentum  ·  {kind} price/RSI divergence detected")
    else:
        ax1.set_title(f"{ticker} — Momentum")

    stoch_df = momentum_data.get("stochastic")
    if stoch_df is not None:
        ax2.plot(df.index, stoch_df["slow_k"], label="Stochastic %K", color="#ff7f0e", linewidth=1.2)
        ax2.plot(df.index, stoch_df["slow_d"], label="Stochastic %D", color="#2ca02c", linewidth=1.2)
        ax2.axhspan(config.STOCH_OVERBOUGHT, 100, color="red", alpha=0.07)
        ax2.axhspan(0, config.STOCH_OVERSOLD, color="green", alpha=0.07)
        ax2.axhline(config.STOCH_OVERBOUGHT, color="red", linestyle="--", alpha=0.5, linewidth=0.8)
        ax2.axhline(config.STOCH_OVERSOLD, color="green", linestyle="--", alpha=0.5, linewidth=0.8)
        ax2.set_ylim(0, 100)
        ax2.set_ylabel("Stochastic")
        ax2.legend(loc="upper left", fontsize=8)
        ax2.grid(True, linestyle=":", alpha=0.6)
    else:
        ax2.set_ylabel("Stochastic")
        ax2.grid(True, linestyle=":", alpha=0.6)

    macd_df = momentum_data.get("macd")
    if macd_df is not None:
        ax3.plot(df.index, macd_df["macd"], label="MACD", color="#17becf", linewidth=1.2)
        ax3.plot(df.index, macd_df["signal"], label="Signal", color="#bcbd22", linewidth=1.2)
        hist = macd_df["hist"]
        colors = np.where(hist.to_numpy() >= 0, "#2ca02c", "#d62728")
        ax3.bar(df.index, hist, label="Histogram", color=colors, alpha=0.5, width=1.0)
        ax3.axhline(0, color="black", linewidth=0.6)
        ax3.set_ylabel("MACD")
        ax3.legend(loc="upper left", fontsize=8)
        ax3.grid(True, linestyle=":", alpha=0.6)
    ax3.set_xlabel("Date")
    _save(fig, out_path)


def draw_weekly_chart(
    ticker: str,
    weekly_df: pd.DataFrame,
    sma10: pd.Series,
    sma40: pd.Series,
    weekly_rsi: pd.Series,
    out_path: Path,
) -> None:
    """Weekly close + SMA10/40 upper panel, weekly RSI lower panel."""
    fig, (ax1, ax2) = plt.subplots(
        nrows=2, ncols=1, sharex=True, figsize=(12, 7),
        gridspec_kw={"height_ratios": [2, 1]},
    )
    
    close = weekly_df["Close"]
    ax1.plot(weekly_df.index, close, label="Weekly Close", color="#1f77b4", linewidth=1.5)
    if sma10 is not None:
        ax1.plot(weekly_df.index, sma10, label="SMA (10)", color="#ff7f0e", linewidth=1.2)
    if sma40 is not None:
        ax1.plot(weekly_df.index, sma40, label="SMA (40)", color="#2ca02c", linewidth=1.2)
        
    ax1.set_ylabel("Price")
    ax1.set_title(f"{ticker} — Weekly Timeframe Context")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, linestyle=":", alpha=0.6)
    
    if weekly_rsi is not None:
        ax2.plot(weekly_df.index, weekly_rsi, label=f"Weekly RSI ({config.RSI_PERIOD})", color="#9467bd", linewidth=1.2)
        ax2.axhspan(config.RSI_OVERBOUGHT, 100, color="red", alpha=0.07)
        ax2.axhspan(0, config.RSI_OVERSOLD, color="green", alpha=0.07)
        ax2.axhline(config.RSI_OVERBOUGHT, color="red", linestyle="--", alpha=0.5, linewidth=0.8)
        ax2.axhline(config.RSI_OVERSOLD, color="green", linestyle="--", alpha=0.5, linewidth=0.8)
        ax2.set_ylim(0, 100)
        ax2.set_ylabel("RSI")
        ax2.legend(loc="upper left", fontsize=8)
        ax2.grid(True, linestyle=":", alpha=0.6)
        
    ax2.set_xlabel("Date")
    _save(fig, out_path)


def draw_regime_chart(
    ticker: str,
    df: pd.DataFrame,
    context_data: Dict[str, Any],
    out_path: Path,
) -> None:
    """ADX/+DI/-DI panel (trend strength) over an ATR panel (volatility)."""
    fig, (ax1, ax2) = plt.subplots(
        nrows=2, ncols=1, sharex=True, figsize=(12, 7),
        gridspec_kw={"height_ratios": [1, 1]},
    )

    adx_df = context_data.get("adx")
    if adx_df is not None:
        ax1.plot(df.index, adx_df["adx"], label="ADX", color="#000000", linewidth=1.4)
        ax1.plot(df.index, adx_df["plus_di"], label="+DI", color="#2ca02c", linewidth=1.0)
        ax1.plot(df.index, adx_df["minus_di"], label="-DI", color="#d62728", linewidth=1.0)
        ax1.axhline(config.ADX_TREND_THRESHOLD, color="gray", linestyle="--", alpha=0.7,
                    linewidth=0.8, label=f"Trend threshold ({config.ADX_TREND_THRESHOLD:.0f})")
        ax1.set_ylabel("ADX / DI")
        ax1.legend(loc="upper left", fontsize=8)
        ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.set_title(f"{ticker} — Regime: trend strength (ADX) & volatility (ATR)")

    atr_s = context_data.get("atr")
    if atr_s is not None:
        ax2.plot(df.index, atr_s, label="ATR (14)", color="#8c564b", linewidth=1.2)
        ax2.fill_between(df.index, 0, atr_s, color="#8c564b", alpha=0.08)
        ax2.set_ylabel("ATR")
        ax2.legend(loc="upper left", fontsize=8)
        ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.set_xlabel("Date")
    _save(fig, out_path)


def draw_levels_chart(
    ticker: str,
    df: pd.DataFrame,
    levels_v2: dict,
    out_path: Path,
) -> None:
    """Price line + horizontal lines for the strongest N support (green) and resistance (red) levels.
    
    Line thickness/alpha is proportional to the touches (strength).
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df.index, df["Close"], label="Close Price", color="#1f77b4", linewidth=1.5)
    
    raw_supports = levels_v2.get("supports", [])
    raw_resistances = levels_v2.get("resistances", [])
    current_price = float(df["Close"].iloc[-1])
    
    # Merge levels and combine touches for identical prices
    combined_levels: dict[float, dict[str, Any]] = {}
    for lvl in raw_supports + raw_resistances:
        price = lvl["price"]
        touches = lvl["touches"]
        if price in combined_levels:
            combined_levels[price]["touches"] += touches
        else:
            combined_levels[price] = {"price": price, "touches": touches}
            
    all_levels = list(combined_levels.values())
    supports = [lvl for lvl in all_levels if lvl["price"] <= current_price]
    resistances = [lvl for lvl in all_levels if lvl["price"] > current_price]
    
    # Determine maximum touches to scale alpha and linewidth
    all_touches = [c["touches"] for c in supports + resistances]
    max_touches = max(all_touches) if all_touches else 1
    
    # Plot supports (green horizontal lines)
    for level in supports:
        price = level["price"]
        touches = level["touches"]
        alpha = 0.3 + 0.5 * (touches / max_touches)
        lw = 1.0 + 2.0 * (touches / max_touches)
        
        ax.axhline(price, color="green", linestyle="--", linewidth=lw, alpha=alpha,
                   label="Support" if "Support" not in ax.get_legend_handles_labels()[1] else "")
        ax.text(df.index[-1], price, f" S: {price:.2f} ({touches})", color="green", 
                va="center", ha="left", fontsize=8, alpha=alpha)
                
    # Plot resistances (red horizontal lines)
    for level in resistances:
        price = level["price"]
        touches = level["touches"]
        alpha = 0.3 + 0.5 * (touches / max_touches)
        lw = 1.0 + 2.0 * (touches / max_touches)
        
        ax.axhline(price, color="red", linestyle="--", linewidth=lw, alpha=alpha,
                   label="Resistance" if "Resistance" not in ax.get_legend_handles_labels()[1] else "")
        ax.text(df.index[-1], price, f" R: {price:.2f} ({touches})", color="red", 
                va="center", ha="left", fontsize=8, alpha=alpha)
                
    ax.set_title(f"{ticker} — Significant Support & Resistance Levels (Filtered)")
    ax.set_ylabel("Price")
    ax.set_xlabel("Date")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    _save(fig, out_path)


def draw_candles_chart(
    ticker: str,
    df: pd.DataFrame,
    trend_data: Dict[str, Any],
    out_path: Path,
    n: int = CANDLE_WINDOW,
) -> None:
    """Manual candlestick of the most recent `n` bars with MA overlays.

    Drawn by hand (no mplfinance) so we add no new dependency. Uses integer
    x-positions so weekend/holiday gaps don't distort candle widths.
    """
    sub = df.iloc[-n:]
    x = np.arange(len(sub))
    o = sub["Open"].to_numpy()
    c = sub["Close"].to_numpy()
    h = sub["High"].to_numpy()
    low = sub["Low"].to_numpy()
    up = c >= o

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.vlines(x, low, h, color="#333333", linewidth=0.7, zorder=1)
    bottoms = np.minimum(o, c)
    heights = np.maximum(np.abs(c - o), 1e-9)
    ax.bar(x[up], heights[up], bottom=bottoms[up], width=0.6, color="#2ca02c", zorder=2)
    ax.bar(x[~up], heights[~up], bottom=bottoms[~up], width=0.6, color="#d62728", zorder=2)

    for key, label, color in (
        ("sma20", "SMA 20", "#9467bd"),
        ("sma50", "SMA 50", "#ff7f0e"),
    ):
        series = trend_data.get(key)
        if series is not None:
            ax.plot(x, series.iloc[-n:].to_numpy(), label=label, linewidth=1.0, color=color)

    # Patterns overlay
    candle_patterns = trend_data.get("candle_patterns")
    if candle_patterns is not None:
        offset = (h - low).mean() * 0.15 if len(h) > 0 else 1.0
        
        doji_s = candle_patterns.get("doji")
        if doji_s is not None:
            doji_idx = np.where(doji_s.iloc[-n:].to_numpy())[0]
            if len(doji_idx) > 0:
                ax.scatter(doji_idx, h[doji_idx] + offset, marker="o", color="gray", s=15, label="Doji")
                
        hammer_s = candle_patterns.get("hammer")
        if hammer_s is not None:
            ham_idx = np.where(hammer_s.iloc[-n:].to_numpy())[0]
            if len(ham_idx) > 0:
                ax.scatter(ham_idx, low[ham_idx] - offset, marker="^", color="green", s=25, label="Hammer")
                
        star_s = candle_patterns.get("shooting_star")
        if star_s is not None:
            star_idx = np.where(star_s.iloc[-n:].to_numpy())[0]
            if len(star_idx) > 0:
                ax.scatter(star_idx, h[star_idx] + offset, marker="v", color="red", s=25, label="Shooting Star")
                
        bull_eng_s = candle_patterns.get("bullish_engulfing")
        if bull_eng_s is not None:
            bull_idx = np.where(bull_eng_s.iloc[-n:].to_numpy())[0]
            if len(bull_idx) > 0:
                ax.scatter(bull_idx, low[bull_idx] - offset, marker="D", color="green", s=25, label="Bullish Engulfing")
                
        bear_eng_s = candle_patterns.get("bearish_engulfing")
        if bear_eng_s is not None:
            bear_idx = np.where(bear_eng_s.iloc[-n:].to_numpy())[0]
            if len(bear_idx) > 0:
                ax.scatter(bear_idx, h[bear_idx] + offset, marker="D", color="red", s=25, label="Bearish Engulfing")

    ticks = list(range(0, len(sub), max(1, len(sub) // 6)))
    ax.set_xticks(ticks)
    ax.set_xticklabels([sub.index[t].date().isoformat() for t in ticks], rotation=45, fontsize=8)
    ax.set_title(f"{ticker} — Last {len(sub)} bars (candlesticks)")
    ax.set_ylabel("Price")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    _save(fig, out_path)


def draw_baserates_chart(
    ticker: str,
    fwd10: pd.Series,
    cond_rsi: pd.Series,
    cond_boll: pd.Series,
    out_path: Path,
) -> None:
    """Plot histograms of conditional forward returns vs baseline returns."""
    df_rsi = pd.DataFrame({"cond": cond_rsi, "fwd": fwd10}).dropna()
    rsi_fwd = df_rsi.loc[df_rsi["cond"], "fwd"]
    
    df_boll = pd.DataFrame({"cond": cond_boll, "fwd": fwd10}).dropna()
    boll_fwd = df_boll.loc[df_boll["cond"], "fwd"]
    
    baseline = fwd10.dropna()
    
    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(12, 8))
    
    if len(rsi_fwd) > 0 and len(baseline) > 0:
        ax1.hist(baseline * 100, bins=20, alpha=0.3, color="gray", label="Baseline (All Days)", density=True)
        ax1.hist(rsi_fwd * 100, bins=15, alpha=0.6, color="orange", label="RSI >= 70", density=True)
        
        base_mean = baseline.mean() * 100
        rsi_mean = rsi_fwd.mean() * 100
        ax1.axvline(base_mean, color="gray", linestyle="--", linewidth=1, label=f"Base Mean ({base_mean:.2f}%)")
        ax1.axvline(rsi_mean, color="darkorange", linestyle="-", linewidth=1.2, label=f"RSI Mean ({rsi_mean:.2f}%)")
        
        ax1.set_title(f"{ticker} — 10-day Forward Returns: RSI >= 70 (n={len(rsi_fwd)}) vs Baseline")
        ax1.set_xlabel("Return (%)")
        ax1.set_ylabel("Density")
        ax1.legend(loc="upper left", fontsize=8)
        ax1.grid(True, linestyle=":", alpha=0.6)
    else:
        ax1.text(0.5, 0.5, "Insufficient data for RSI >= 70 base rates", ha="center", va="center")
        ax1.set_title(f"{ticker} — 10-day Forward Returns (RSI >= 70) — Insufficient Data")
        
    if len(boll_fwd) > 0 and len(baseline) > 0:
        ax2.hist(baseline * 100, bins=20, alpha=0.3, color="gray", label="Baseline (All Days)", density=True)
        ax2.hist(boll_fwd * 100, bins=15, alpha=0.6, color="red", label="Close > Bollinger Upper", density=True)
        
        base_mean = baseline.mean() * 100
        boll_mean = boll_fwd.mean() * 100
        ax2.axvline(base_mean, color="gray", linestyle="--", linewidth=1, label=f"Base Mean ({base_mean:.2f}%)")
        ax2.axvline(boll_mean, color="red", linestyle="-", linewidth=1.2, label=f"Boll Mean ({boll_mean:.2f}%)")
        
        ax2.set_title(f"{ticker} — 10-day Forward Returns: Close > Bollinger Upper (n={len(boll_fwd)}) vs Baseline")
        ax2.set_xlabel("Return (%)")
        ax2.set_ylabel("Density")
        ax2.legend(loc="upper left", fontsize=8)
        ax2.grid(True, linestyle=":", alpha=0.6)
    else:
        ax2.text(0.5, 0.5, "Insufficient data for Close > Bollinger Upper base rates", ha="center", va="center")
        ax2.set_title(f"{ticker} — 10-day Forward Returns (Bollinger Upper) — Insufficient Data")
        
    plt.tight_layout()
    _save(fig, out_path)


def draw_relative_chart(
    ticker: str,
    benchmark_ticker: str,
    asset_rebased: pd.Series,
    bench_rebased: pd.Series,
    rs: pd.Series,
    rs_ma: pd.Series,
    out_path: Path,
) -> None:
    """Plot rebased relative performance and RS ratio vs its SMA."""
    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, sharex=True, figsize=(12, 8))
    
    ax1.plot(asset_rebased.index, asset_rebased, label=f"{ticker} (Rebased)", color="#1f77b4", linewidth=1.5)
    ax1.plot(bench_rebased.index, bench_rebased, label=f"{benchmark_ticker} (Rebased)", color="#ff7f0e", linewidth=1.2)
    ax1.axhline(100, color="black", linestyle="--", linewidth=0.8, alpha=0.7)
    ax1.set_ylabel("Performance (Base 100)")
    ax1.set_title(f"{ticker} vs {benchmark_ticker} — Rebased Performance Comparison")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, linestyle=":", alpha=0.6)
    
    ax2.plot(rs.index, rs, label="Relative Strength Ratio", color="purple", linewidth=1.5)
    ax2.plot(rs_ma.index, rs_ma, label=f"RS SMA ({config.RS_MA_WINDOW})", color="gray", linestyle="-", linewidth=1.2)
    
    ax2.fill_between(rs.index, rs_ma, rs, where=(rs >= rs_ma), color="green", alpha=0.1, interpolate=True)
    ax2.fill_between(rs.index, rs_ma, rs, where=(rs < rs_ma), color="red", alpha=0.1, interpolate=True)
    
    ax2.set_ylabel("RS Ratio")
    ax2.set_xlabel("Date")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def draw_seasonality_chart(
    ticker: str,
    table: pd.DataFrame,
    out_path: Path,
) -> None:
    """Plot seasonality heatmap of monthly returns using pure matplotlib (no Seaborn)."""
    pct_table = table * 100.0
    avg_row = pct_table.mean(axis=0)
    
    years = list(pct_table.index)
    row_labels = [str(y) for y in years] + ["Avg"]
    col_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    grid_data = np.vstack([pct_table.values, avg_row.values])
    
    fig, ax = plt.subplots(figsize=(12, len(row_labels) * 0.7 + 2))
    
    from matplotlib.colors import TwoSlopeNorm
    
    val_min = np.nanmin(grid_data) if not np.isnan(grid_data).all() else -1.0
    val_max = np.nanmax(grid_data) if not np.isnan(grid_data).all() else 1.0
    if val_min >= 0:
        val_min = -1.0
    if val_max <= 0:
        val_max = 1.0
        
    norm = TwoSlopeNorm(vmin=val_min, vcenter=0.0, vmax=val_max)
    im = ax.imshow(grid_data, cmap="RdYlGn", norm=norm, aspect="auto")
    
    ax.set_xticks(np.arange(12))
    ax.set_xticklabels(col_labels)
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_yticklabels(row_labels)
    
    ax.tick_params(top=True, bottom=True, labeltop=True, labelbottom=True)
    
    for i in range(grid_data.shape[0]):
        for j in range(grid_data.shape[1]):
            val = grid_data[i, j]
            if not np.isnan(val):
                color = "white" if abs(val) > (val_max - val_min) * 0.35 else "black"
                ax.text(j, i, f"{val:.1f}%", ha="center", va="center", color=color, fontsize=9)
            else:
                ax.text(j, i, "N/A", ha="center", va="center", color="gray", fontsize=9)
                
    ax.axhline(len(years) - 0.5, color="black", linewidth=1.5)
    
    fig.colorbar(im, ax=ax, label="Return (%)", pad=0.02)
    ax.set_title(f"{ticker} — Monthly Return Seasonality (%)", pad=20)
    
    _save(fig, out_path)


def draw_volume_chart(
    ticker: str,
    df: pd.DataFrame,
    vwap: pd.Series,
    obv: pd.Series,
    mfi: pd.Series,
    avwap_ytd: pd.Series,
    avwap_high: pd.Series,
    avwap_low: pd.Series,
    out_path: Path,
) -> None:
    """Plot volume indicators (VWAP, Anchored VWAPs, MFI, Volume bars, and OBV)."""
    fig, (ax1, ax2, ax3) = plt.subplots(
        nrows=3, ncols=1, sharex=True, figsize=(12, 9),
        gridspec_kw={"height_ratios": [2, 1, 1]},
    )
    
    # ax1: Price + VWAPs
    ax1.plot(df.index, df["Close"], label=f"{ticker} Close", color="#1f77b4", linewidth=1.5)
    ax1.plot(vwap.index, vwap, label="VWAP (20)", color="orange", linestyle="--", linewidth=1.2)
    
    if avwap_ytd is not None and not avwap_ytd.dropna().empty:
        ax1.plot(avwap_ytd.index, avwap_ytd, label="AVWAP YTD", color="#2ca02c", linestyle="-.", linewidth=1.2)
    if avwap_high is not None and not avwap_high.dropna().empty:
        ax1.plot(avwap_high.index, avwap_high, label="AVWAP 52w High", color="#d62728", linestyle="-.", linewidth=1.2)
    if avwap_low is not None and not avwap_low.dropna().empty:
        ax1.plot(avwap_low.index, avwap_low, label="AVWAP 52w Low", color="#9467bd", linestyle="-.", linewidth=1.2)
        
    ax1.set_ylabel("Price")
    ax1.set_title(f"{ticker} — Close Price vs VWAP / Anchored VWAP & MFI & Volume/OBV")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, linestyle=":", alpha=0.6)
    
    # ax2: MFI
    if mfi is not None:
        ax2.plot(mfi.index, mfi, label=f"MFI ({config.MFI_PERIOD})", color="#e377c2", linewidth=1.2)
        ax2.axhspan(config.MFI_OVERBOUGHT, 100, color="red", alpha=0.07)
        ax2.axhspan(0, config.MFI_OVERSOLD, color="green", alpha=0.07)
        ax2.axhline(config.MFI_OVERBOUGHT, color="red", linestyle="--", alpha=0.5, linewidth=0.8)
        ax2.axhline(config.MFI_OVERSOLD, color="green", linestyle="--", alpha=0.5, linewidth=0.8)
        ax2.set_ylim(0, 100)
        ax2.set_ylabel("MFI")
        ax2.legend(loc="upper left", fontsize=8)
        ax2.grid(True, linestyle=":", alpha=0.6)
    else:
        ax2.set_ylabel("MFI")
        ax2.grid(True, linestyle=":", alpha=0.6)
        
    # ax3: Volume bars + OBV
    colors = []
    close_vals = df["Close"].values
    for i in range(len(df)):
        if i == 0:
            colors.append("gray")
        elif close_vals[i] >= close_vals[i-1]:
            colors.append("green")
        else:
            colors.append("red")
            
    ax3.bar(df.index, df["Volume"], color=colors, alpha=0.6, label="Volume")
    ax3.set_ylabel("Volume")
    ax3.legend(loc="upper left", fontsize=8)
    ax3.grid(True, linestyle=":", alpha=0.6)
    
    ax3_twin = ax3.twinx()
    ax3_twin.plot(obv.index, obv, color="purple", linewidth=1.5, label="OBV")
    ax3_twin.set_ylabel("On-Balance Volume (OBV)", color="purple")
    ax3_twin.tick_params(axis="y", labelcolor="purple")
    ax3_twin.legend(loc="upper right", fontsize=8)
    
    ax3.set_xlabel("Date")
    plt.tight_layout()
    _save(fig, out_path)


def draw_correlogram_chart(
    ticker: str,
    acf_pacf_data: dict,
    out_path: Path,
) -> None:
    """Plot ACF stems for raw, absolute, and squared returns with a confidence band."""
    fig, (ax1, ax2, ax3) = plt.subplots(nrows=3, ncols=1, figsize=(12, 10), sharex=True)
    
    conf = acf_pacf_data["conf"]
    lags_arr = np.arange(len(acf_pacf_data["raw"]["acf"]))
    
    def _draw_sub(ax, acf_vals, title, color):
        ax.stem(lags_arr, acf_vals, linefmt=f"{color}-", markerfmt=f"{color}o", basefmt="k-", label="ACF")
        ax.axhspan(-conf, conf, color="gray", alpha=0.2, label="95% CI")
        ax.set_ylabel("Autocorrelation")
        ax.set_title(title)
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, linestyle=":", alpha=0.6)
        
    _draw_sub(ax1, acf_pacf_data["raw"]["acf"], f"{ticker} Raw Returns ACF", "b")
    _draw_sub(ax2, acf_pacf_data["abs"]["acf"], f"{ticker} Absolute Returns |r| ACF", "g")
    _draw_sub(ax3, acf_pacf_data["sq"]["acf"], f"{ticker} Squared Returns r² ACF", "m")
    
    ax3.set_xlabel("Lag")
    plt.tight_layout()
    _save(fig, out_path)


def draw_distribution_chart(
    ticker: str,
    dist_data: dict,
    returns: pd.Series,
    out_path: Path,
) -> None:
    """Plot returns density histogram with fitted Normal and Student-t distributions."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ret_vals = returns.dropna().values
    
    n_bins = min(50, len(ret_vals) // 5) if len(ret_vals) > 50 else 15
    ax.hist(ret_vals, bins=n_bins, density=True, alpha=0.5, color="gray", edgecolor="black", label="Return Density")
    
    x_min, x_max = np.nanmin(ret_vals), np.nanmax(ret_vals)
    x_arr = np.linspace(x_min, x_max, 500)
    
    norm_fit = dist_data["normal_fit"]
    y_norm = scipy.stats.norm.pdf(x_arr, loc=norm_fit["loc"], scale=norm_fit["scale"])
    ax.plot(x_arr, y_norm, color="blue", linewidth=2, label=f"Normal Fit (std={norm_fit['scale']:.4f})")
    
    t_fit = dist_data["t_fit"]
    y_t = scipy.stats.t.pdf(x_arr, df=t_fit["df"], loc=t_fit["loc"], scale=t_fit["scale"])
    ax.plot(x_arr, y_t, color="red", linewidth=2, linestyle="--", label=f"Student-t Fit (df={t_fit['df']:.2f})")
    
    ax.set_xlabel("Return")
    ax.set_ylabel("Density")
    title_str = (
        f"{ticker} Returns Distribution\n"
        f"Skewness: {dist_data['skew']:.4f} | Excess Kurtosis: {dist_data['excess_kurtosis']:.4f} | "
        f"JB: {dist_data['jb_stat']:.2f} (p={dist_data['jb_pvalue']:.4f})"
    )
    ax.set_title(title_str)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def draw_52week_chart(
    ticker: str,
    df: pd.DataFrame,
    stats_52w: dict,
    out_path: Path,
) -> None:
    """Plot price history with horizontal 52-week High/Low boundary lines.

    Only the 52-week window itself is plotted (not the full fetched history) so
    the High/Low lines actually bound the visible price — otherwise older prices
    outside the window would cross the lines and look wrong.
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    window = int(stats_52w.get("window_used", len(df)))
    sub = df.iloc[-window:]
    ax.plot(sub.index, sub["Close"], label=f"{ticker} Close (last {window} bars)", color="#1f77b4", linewidth=1.5)

    high_val = stats_52w["high"]
    low_val = stats_52w["low"]
    curr_val = stats_52w["current"]

    ax.axhline(high_val, color="red", linestyle="--", alpha=0.7, label=f"52w High ({high_val:.2f})")
    ax.axhline(low_val, color="green", linestyle="--", alpha=0.7, label=f"52w Low ({low_val:.2f})")

    ax.scatter(sub.index[-1], curr_val, color="black", s=100, zorder=5, label=f"Current ({curr_val:.2f})")
    
    ax.set_ylabel("Price")
    ax.set_xlabel("Date")
    pos_pct_s = f"{stats_52w['position_pct']:.1f}%" if not np.isnan(stats_52w['position_pct']) else "N/A"
    ax.set_title(f"{ticker} — 52-Week Range Position ({pos_pct_s} of Range)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def draw_drawdown_chart(
    ticker: str,
    dd_series: pd.DataFrame,
    out_path: Path,
) -> None:
    """Plot underwater drawdown equity curve."""
    fig, ax = plt.subplots(figsize=(12, 5))
    
    dd_pct = dd_series["drawdown"] * 100.0
    
    ax.plot(dd_pct.index, dd_pct, color="darkred", linewidth=1.2, label="Drawdown %")
    ax.fill_between(dd_pct.index, dd_pct, 0.0, color="red", alpha=0.25)
    ax.axhline(0.0, color="black", linestyle="-", linewidth=1.0)
    
    ax.set_ylabel("Drawdown %")
    ax.set_xlabel("Date")
    ax.set_title(f"{ticker} — Historical Drawdown (Underwater Curve)")
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def draw_beta_chart(
    ticker: str,
    stock_ret: pd.Series,
    bench_ret: pd.Series,
    beta: float,
    alpha_daily: float,
    out_path: Path,
) -> None:
    """Plot returns scatter plot of asset vs benchmark with regression line."""
    fig, ax = plt.subplots(figsize=(8, 6))
    
    aligned = pd.concat([stock_ret, bench_ret], axis=1, join="inner").dropna()
    if len(aligned) < 2:
        _save(fig, out_path)
        return
        
    s_vals = aligned.iloc[:, 0].values
    b_vals = aligned.iloc[:, 1].values
    
    ax.scatter(b_vals, s_vals, color="gray", alpha=0.5, edgecolors="none", label="Daily Returns")
    
    x_arr = np.linspace(np.nanmin(b_vals), np.nanmax(b_vals), 100)
    y_arr = beta * x_arr + alpha_daily
    ax.plot(x_arr, y_arr, color="blue", linewidth=2, label=f"Regression (Beta={beta:.2f})")
    
    ax.set_xlabel("Benchmark Returns")
    ax.set_ylabel(f"{ticker} Returns")
    ax.set_title(f"{ticker} Systematic Risk (Beta vs Benchmark)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def draw_structural_breaks_chart(
    ticker: str,
    df: pd.DataFrame,
    breaks: list[dict],
    out_path: Path,
) -> None:
    """Plot price series with vertical structural breaks and shaded regime bands."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.plot(df.index, df["Close"], color="#1f77b4", linewidth=1.5, label=f"{ticker} Close")

    sorted_breaks = sorted(breaks, key=lambda x: x["index"])
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b"]

    max_idx = len(df) - 1

    def _df_pos(b: dict) -> int:
        """Map a break to its position in the PRICE index.

        The break's stored ``date`` (taken from the returns index) is the
        source of truth; locate it in df.index directly. Break ``index``
        values are positions in the RETURNS series, which is one shorter
        than prices (diff().dropna() drops the first row) — so the
        positional fallback must shift by +1, then clamp.
        """
        try:
            pos = int(df.index.get_indexer([pd.Timestamp(b["date"])])[0])
            if pos != -1:
                return pos
        except (ValueError, TypeError):
            pass
        return min(b["index"] + 1, max_idx)

    break_positions = [_df_pos(b) for b in sorted_breaks]
    band_bounds = [0] + break_positions + [max_idx]

    for i in range(len(band_bounds) - 1):
        start_date = df.index[band_bounds[i]]
        end_date = df.index[band_bounds[i + 1]]

        color = colors[i % len(colors)]
        ax.axvspan(start_date, end_date, color=color, alpha=0.1, label=f"Regime {i+1}" if i < 5 else "")

    for b, b_pos in zip(sorted_breaks, break_positions):
        b_date = df.index[b_pos]
        ax.axvline(b_date, color="red", linestyle="--", linewidth=1.5, alpha=0.8, label=f"Break: {b['type']}")
        
    ax.set_ylabel("Price")
    ax.set_xlabel("Date")
    ax.set_title(f"{ticker} — Structural Breaks & Price Regimes")
    
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc="upper left", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def draw_hurst_chart(
    ticker: str,
    ret_h: dict,
    vol_h: dict,
    out_path: Path,
) -> None:
    """Plot rescaled range log-log line for returns and volatility."""
    fig, ax = plt.subplots(figsize=(8, 6))
    
    if len(ret_h.get("scales", [])) >= 2:
        scales = np.array(ret_h["scales"])
        rs_vals = np.array(ret_h["rs_values"])
        ax.scatter(np.log(scales), np.log(rs_vals), color="blue", alpha=0.7, label=f"Returns R/S (H={ret_h['hurst']:.2f})")
        coeffs = np.polyfit(np.log(scales), np.log(rs_vals), 1)
        ax.plot(np.log(scales), np.polyval(coeffs, np.log(scales)), color="blue", linestyle="--")
        
    if len(vol_h.get("scales", [])) >= 2:
        scales = np.array(vol_h["scales"])
        rs_vals = np.array(vol_h["rs_values"])
        ax.scatter(np.log(scales), np.log(rs_vals), color="purple", alpha=0.7, label=f"Volatility R/S (H={vol_h['hurst']:.2f})")
        coeffs = np.polyfit(np.log(scales), np.log(rs_vals), 1)
        ax.plot(np.log(scales), np.polyval(coeffs, np.log(scales)), color="purple", linestyle="--")
        
    ax.set_xlabel("log(Scale)")
    ax.set_ylabel("log(R/S)")
    ax.set_title(f"{ticker} — R/S Hurst Exponent Estimation")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def draw_quantile_beta_chart(
    ticker: str,
    qbeta_res: dict,
    out_path: Path,
) -> None:
    """Plot quantile beta values with confidence interval bands and OLS beta reference."""
    fig, ax = plt.subplots(figsize=(8, 6))
    
    quantiles = qbeta_res["quantiles"]
    betas = [qbeta_res["betas"][q] for q in quantiles]
    ci_low = [qbeta_res["cis"][q][0] for q in quantiles]
    ci_high = [qbeta_res["cis"][q][1] for q in quantiles]
    
    ols_val = qbeta_res["ols_beta"]
    ax.axhline(ols_val, color="red", linestyle="--", linewidth=1.5, label=f"OLS Beta ({ols_val:.2f})")
    
    ax.plot(quantiles, betas, color="blue", marker="o", linewidth=2, label="Quantile Beta")
    ax.fill_between(quantiles, ci_low, ci_high, color="blue", alpha=0.15, label="95% Confidence Interval")
    
    ax.set_xlabel("Quantile (tau)")
    ax.set_ylabel("Beta Coefficient")
    ax.set_title(f"{ticker} — Conditional Beta Across Quantiles (Quantile Regression)")
    ax.set_xticks(quantiles)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def draw_all_charts(
    ticker: str,
    df: pd.DataFrame,
    trend_data: Dict[str, Any],
    momentum_data: Dict[str, Any],
    volatility_data: Dict[str, Any],
    levels_data: Dict[str, Any],
    context_data: Dict[str, Any] | None,
    out_dir: Path,
) -> list[tuple[str, Path]]:
    """Draw every applicable chart. Returns (caption, path) for each one made."""
    charts: list[tuple[str, Path]] = []

    overview = out_dir / f"{ticker}_overview.png"
    draw_overview_chart(ticker, df, trend_data, volatility_data, levels_data, overview)
    charts.append(("Price overview (MAs, Bollinger, filtered levels) and volume", overview))

    if context_data is not None and "mtf" in context_data:
        mtf_data = context_data["mtf"]
        if mtf_data.get("status") == "ok":
            weekly_img = out_dir / f"{ticker}_weekly.png"
            draw_weekly_chart(
                ticker,
                mtf_data["_weekly_df"],
                mtf_data["_sma10"],
                mtf_data["_sma40"],
                mtf_data["_rsi"],
                weekly_img,
            )
            charts.append(("Multiple timeframe context: weekly price, SMA10/40, and weekly RSI(14)", weekly_img))

    if momentum_data.get("rsi") is not None or momentum_data.get("macd") is not None:
        momentum = out_dir / f"{ticker}_momentum.png"
        draw_momentum_chart(ticker, df, momentum_data, context_data, momentum)
        charts.append(("Momentum: RSI (with zones) and MACD", momentum))

    if context_data is not None and (
        context_data.get("adx") is not None or context_data.get("atr") is not None
    ):
        regime = out_dir / f"{ticker}_regime.png"
        draw_regime_chart(ticker, df, context_data, regime)
        charts.append(("Regime: trend strength (ADX/DI) and volatility (ATR)", regime))

    if len(df) >= 5:
        candles = out_dir / f"{ticker}_candles.png"
        draw_candles_chart(ticker, df, trend_data, candles)
        charts.append((f"Recent {min(len(df), CANDLE_WINDOW)}-bar candlesticks", candles))

    if levels_data.get("v2") is not None:
        levels_img = out_dir / f"{ticker}_levels.png"
        draw_levels_chart(ticker, df, levels_data["v2"], levels_img)
        charts.append(("Significant support and resistance levels (filtered)", levels_img))

    if context_data is not None and context_data.get("baserates") is not None:
        br_data = context_data["baserates"]
        br_img = out_dir / f"{ticker}_baserates.png"
        draw_baserates_chart(
            ticker,
            br_data["fwd10"],
            br_data["cond_rsi"],
            br_data["cond_boll"],
            br_img,
        )
        charts.append(("Empirical base rates: forward return distributions", br_img))

    if context_data is not None and context_data.get("relative") is not None:
        rel_data = context_data["relative"]
        rel_img = out_dir / f"{ticker}_relative.png"
        draw_relative_chart(
            ticker,
            rel_data["benchmark_ticker"],
            rel_data["asset_rebased"],
            rel_data["bench_rebased"],
            rel_data["rs"],
            rel_data["rs_ma"],
            rel_img,
        )
        charts.append(("Relative strength vs benchmark index", rel_img))

    if context_data is not None and context_data.get("seasonality_table") is not None:
        seas_table = context_data["seasonality_table"]
        seas_img = out_dir / f"{ticker}_seasonality.png"
        draw_seasonality_chart(ticker, seas_table, seas_img)
        charts.append(("Calendar monthly returns seasonality heatmap", seas_img))

    if context_data is not None and context_data.get("volume") is not None:
        vol_data = context_data["volume"]
        vol_img = out_dir / f"{ticker}_volume.png"
        draw_volume_chart(
            ticker,
            df,
            vol_data["vwap"],
            vol_data["obv"],
            vol_data.get("_mfi_series"),
            vol_data.get("anchored_vwap", {}).get("_ytd_series"),
            vol_data.get("anchored_vwap", {}).get("_high_series"),
            vol_data.get("anchored_vwap", {}).get("_low_series"),
            vol_img,
        )
        charts.append(("Volume analysis: Close vs VWAP and volume vs OBV", vol_img))

    if context_data is not None and context_data.get("econometrics") is not None:
        econ_data = context_data["econometrics"]
        if econ_data.get("status") == "ok":
            corr_img = out_dir / f"{ticker}_correlogram.png"
            dist_img = out_dir / f"{ticker}_distribution.png"
            
            returns = np.log(df["Close"]).diff().dropna()
            
            draw_correlogram_chart(ticker, econ_data["acf_pacf"], corr_img)
            draw_distribution_chart(ticker, econ_data["distribution"], returns, dist_img)
            
            charts.append(("Predictability analysis: ACF/PACF correlogram", corr_img))
            charts.append(("Return distribution analysis: histogram with Normal & Student-t overlay", dist_img))
            
            if "breaks" in econ_data:
                breaks_img = out_dir / f"{ticker}_structural_breaks.png"
                draw_structural_breaks_chart(ticker, df, econ_data["breaks"], breaks_img)
                charts.append(("Structural breaks and price regimes analysis", breaks_img))
                
            if "hurst" in econ_data and econ_data["hurst"] is not None:
                hurst_img = out_dir / f"{ticker}_hurst.png"
                draw_hurst_chart(ticker, econ_data["hurst"]["returns"], econ_data["hurst"]["volatility"], hurst_img)
                charts.append(("R/S Hurst exponent long memory analysis", hurst_img))
                
            if "quantile_beta" in econ_data and econ_data["quantile_beta"] is not None:
                qb_img = out_dir / f"{ticker}_quantile_beta.png"
                draw_quantile_beta_chart(ticker, econ_data["quantile_beta"], qb_img)
                charts.append(("Conditional beta across quantiles (Quantile Regression)", qb_img))

    if context_data is not None and context_data.get("risk") is not None:
        risk_data = context_data["risk"]
        if risk_data.get("status") == "ok":
            r52_img = out_dir / f"{ticker}_52week.png"
            draw_52week_chart(ticker, df, risk_data["52week"], r52_img)
            charts.append(("52-Week range position and boundary levels", r52_img))
            
            dd_img = out_dir / f"{ticker}_drawdown.png"
            draw_drawdown_chart(ticker, risk_data["drawdown_series"], dd_img)
            charts.append(("Historical drawdown underwater curve", dd_img))
            
            beta_data = risk_data.get("beta")
            if beta_data is not None and not np.isnan(beta_data["beta"]):
                beta_img = out_dir / f"{ticker}_beta.png"
                draw_beta_chart(
                    ticker,
                    risk_data["stock_returns"],
                    risk_data["bench_returns"],
                    beta_data["beta"],
                    (beta_data["alpha_annualized"] / 252.0),
                    beta_img,
                )
                charts.append(("Systematic risk: returns scatter plot and regression line vs benchmark", beta_img))

    if context_data is not None and "volume_profile" in context_data:
        vp_data = context_data["volume_profile"]
        if vp_data.get("status") == "ok":
            vp_img = out_dir / f"{ticker}_volume_profile.png"
            draw_volume_profile_chart(ticker, df, vp_data, vp_img)
            charts.append(("Volume Profile: Point of Control (POC) and Value Area (VAH/VAL)", vp_img))

    if context_data is not None and "volume_profile_weekly" in context_data:
        vpw_data = context_data["volume_profile_weekly"]
        if vpw_data.get("status") == "ok":
            vpw_img = out_dir / f"{ticker}_volume_profile_weekly.png"
            draw_volume_profile_weekly_chart(ticker, df, vpw_data, vpw_img)
            charts.append(("Weekly Volume Profile: Point of Control (POC) and Value Area (VAH/VAL)", vpw_img))

    if context_data is not None and "fibonacci" in context_data:
        fib_data = context_data["fibonacci"]
        if fib_data.get("status") in ("ok", "warning"):
            fib_img = out_dir / f"{ticker}_fibonacci.png"
            draw_fibonacci_chart(ticker, df, fib_data, fib_img)
            charts.append(("Fibonacci Retracement: levels and touch respect statistics", fib_img))

    if context_data is not None and "donchian" in context_data:
        don_data = context_data["donchian"]
        if don_data.get("status") in ("ok", "warning"):
            don_img = out_dir / f"{ticker}_donchian.png"
            draw_donchian_chart(ticker, df, don_data, don_img)
            charts.append(("Donchian Channels: 20-day (shaded region) and 55-day (dashed lines) channels", don_img))

    return charts


def build_report(
    ticker: str,
    price_data: dl.PriceData,
    trend_data: Dict[str, Any],
    momentum_data: Dict[str, Any],
    volatility_data: Dict[str, Any],
    levels_data: Dict[str, Any],
    *,
    context_data: Dict[str, Any] | None = None,
    out_dir: Path | str = config.REPORTS_DIR,
    draw_chart: bool = True,
    no_interactive: bool = False,
    warnings: list[str] | None = None,
    console: Console | None = None,
) -> str:
    """Generate Markdown and visual chart report for a ticker.
    
    Returns:
        str: Absolute path to the generated markdown report.
    """
    out_dir_path = Path(out_dir).resolve()
    out_dir_path.mkdir(parents=True, exist_ok=True)
    
    clean_ticker = ticker.upper()
    report_file = out_dir_path / f"{clean_ticker}_report.md"

    # Human-in-the-loop gate: chart rendering does real matplotlib work, so ask
    # before doing it unless the caller explicitly opted out via --no-interactive.
    should_draw = draw_chart
    if should_draw and not no_interactive:
        should_draw = Confirm.ask(
            f"Render the {clean_ticker} technical charts? (4 PNG files via matplotlib)",
            default=True,
            console=console,
        )

    charts: list[tuple[str, Path]] = []
    if should_draw:
        charts = draw_all_charts(
            clean_ticker,
            price_data.df,
            trend_data,
            momentum_data,
            volatility_data,
            levels_data,
            context_data,
            out_dir_path,
        )

    # Compile markdown text
    md_lines = [
        f"# Techna Analysis Report for {clean_ticker}",
        "",
        "> [!IMPORTANT]",
        "> **Disclaimer:** This report is generated by an automated technical analysis agent.",
        "> It provides **signals, not advice**. All interpretations and decisions are the user's responsibility.",
        "",
    ]

    # 0. Today's Events section
    if context_data is not None and "events" in context_data:
        ev_list = context_data["events"]
        md_lines.append("## 0. Today's Events")
        if not ev_list:
            md_lines.append("No state changes detected on the last bar.")
        else:
            for ev in ev_list:
                md_lines.append(f"- **{ev['type']}** ({ev['direction']}): {ev['detail']}")
        md_lines.append("")

    md_lines.extend([
        "## 1. Overview",
        f"- **Ticker:** {clean_ticker}",
        f"- **Date range:** {price_data.df.index.min().date()} to {price_data.df.index.max().date()}",
        f"- **Total trading bars:** {len(price_data.df)}",
        f"- **Last closing price:** {price_data.df['Close'].iloc[-1]:.2f}",
        f"- **Data source:** {price_data.source}",
        "",
    ])

    if context_data is not None and context_data.get("data_provenance") is not None:
        md_lines.append(_provenance_markdown(context_data["data_provenance"]))
        md_lines.append("")

    # 1.5. At a Glance — Risk Context
    if context_data is not None and context_data.get("risk") is not None:
        risk = context_data["risk"]
        if risk.get("status") == "ok":
            r52 = risk["52week"]
            r52_state = r52["state"]
            r52_pct = f"{r52['position_pct']:.1f}%" if not np.isnan(r52['position_pct']) else "N/A"
            
            dd_series = risk["drawdown_series"]
            curr_dd = dd_series["drawdown"].iloc[-1]
            if curr_dd == 0:
                dd_str = "at all-time high"
            else:
                peak_idx = dd_series[dd_series["close"] == dd_series["running_max"]].index
                peak_date_str = peak_idx[-1].strftime("%Y-%m-%d") if len(peak_idx) > 0 else "unknown"
                dd_str = f"currently in drawdown of {abs(curr_dd)*100.0:.2f}% from peak on {peak_date_str}"
                
            liq = risk["liquidity"]
            liq_state = liq["state"]
            liq_val = f"{liq['avg_value_20']:,.2f}"
            
            beta_d = risk["beta"]
            if not np.isnan(beta_d["beta"]):
                beta_str = f"{beta_d['beta']:.2f} ({beta_d['state']})"
            else:
                beta_str = "N/A"
                
            md_lines.append("## 1.5. At a Glance — Risk Context")
            md_lines.append(f"- **52-Week Position:** {r52_state} ({r52_pct})")
            md_lines.append(f"- **Drawdown:** {dd_str}")
            md_lines.append(f"- **Liquidity:** {liq_state} (avg 20d traded value {liq_val} quote currency)")
            md_lines.append(f"- **Beta vs SPY:** {beta_str}")
            md_lines.append("")
    
    if warnings:
        md_lines.append("### Warnings")
        for w in warnings:
            md_lines.append(f"- **Warning:** {w}")
        md_lines.append("")
    
    # 2. Trend indicators section
    md_lines.extend([
        "## 2. Trend Analysis",
        f"- **Current Trend State:** `{trend_data.get('state', 'sideways')}`",
    ])
    if "last_cross" in trend_data:
        cross_type, cross_date = trend_data["last_cross"]
        if cross_type != "none":
            md_lines.append(f"- **Last Crossover:** `{cross_type}` on `{cross_date}`")
        else:
            md_lines.append("- **Last Crossover:** None detected in the historical period")
    
    t_f = trend_finding(trend_data.get('state', 'sideways'), trend_data.get('last_cross', ('none', 'N/A')))
    md_lines.extend(["", t_f, ""])
    
    # 2.5. Weekly Timeframe Context
    if context_data is not None and "mtf" in context_data:
        mtf_data = context_data["mtf"]
        if mtf_data.get("status") == "ok":
            md_lines.extend([
                "## 2.5. Weekly Timeframe Context",
                f"- **Weekly Trend State:** `{mtf_data.get('weekly_trend_state', 'sideways')}`",
                f"- **Weekly RSI (14):** `{mtf_data.get('weekly_rsi', float('nan')):.2f}` (State: `{mtf_data.get('weekly_rsi_state', 'neutral')}`)",
                f"- **Weekly MACD State:** `{mtf_data.get('weekly_macd_state', 'bearish')}`",
                f"- **Weekly Trend Regime (ADX):** `{mtf_data.get('weekly_trend_regime', 'ranging')}` (ADX: `{mtf_data.get('weekly_adx', float('nan')):.2f}`)",
                f"- **Daily/Weekly Trend Alignment:** `{mtf_data.get('alignment', 'mixed')}`",
            ])
            mtf_f = mtf_finding(
                mtf_data.get('weekly_trend_state', 'sideways'),
                mtf_data.get('weekly_rsi_state', 'neutral'),
                mtf_data.get('alignment', 'mixed')
            )
            md_lines.extend(["", mtf_f, ""])
        else:
            md_lines.extend([
                "## 2.5. Weekly Timeframe Context",
                "- **Status:** `warning`",
                f"- **Details:** {mtf_data.get('warning', 'Insufficient data')}",
                "",
                "Insufficient history to compute this finding.",
                ""
            ])

    # 3. Momentum indicators section
    stoch_k_val = momentum_data.get("last_stoch_k", float("nan"))
    stoch_d_val = momentum_data.get("last_stoch_d", float("nan"))
    stoch_state_val = momentum_data.get("stoch_state", "neutral")
    stoch_cross = momentum_data.get("stoch_crossover", "none")

    md_lines.extend([
        "## 3. Momentum Analysis",
        f"- **RSI (14) value:** `{momentum_data.get('last_rsi', float('nan')):.2f}` (State: `{momentum_data.get('rsi_state', 'neutral')}`)",
        f"- **MACD State:** `{momentum_data.get('macd_state', 'bearish')}`",
    ])
    m_h = 0.0
    if "last_macd" in momentum_data:
        m, s, h = momentum_data["last_macd"]
        m_h = h
        md_lines.append(f"  - MACD Line: `{m:.4f}`, Signal Line: `{s:.4f}`, Histogram: `{h:.4f}`")
        
    md_lines.extend([
        f"- **Stochastic Slow %K:** `{stoch_k_val:.2f}` (State: `{stoch_state_val}`)",
        f"  - Slow %D: `{stoch_d_val:.2f}`",
        f"  - Crossover: `{stoch_cross}`",
    ])
    
    m_f = momentum_finding(
        momentum_data.get('rsi_state', 'neutral'),
        momentum_data.get('macd_state', 'bearish'),
        float(momentum_data.get('last_rsi', float('nan'))),
        m_h,
        stoch_state_val,
        stoch_k_val,
    )
    md_lines.extend(["", m_f, ""])
    
    # 4. Volatility section
    md_lines.extend([
        "## 4. Volatility (Bollinger Bands)",
        f"- **Bollinger State:** `{volatility_data.get('state', 'within_bands')}`",
    ])
    v_pct_b, v_upper, v_lower = float('nan'), float('nan'), float('nan')
    if "last_bands" in volatility_data:
        mid, upper, lower, pct_b, bwidth = volatility_data["last_bands"]
        v_pct_b, v_upper, v_lower = pct_b, upper, lower
        md_lines.extend([
            f"  - Upper Band (2σ): `{upper:.2f}`",
            f"  - Mid Band (SMA20): `{mid:.2f}`",
            f"  - Lower Band (2σ): `{lower:.2f}`",
            f"  - %B: `{pct_b:.4f}`",
            f"  - Bandwidth: `{bwidth:.4f}`",
        ])
    
    v_f = volatility_finding(
        volatility_data.get('state', 'within_bands'),
        v_pct_b,
        v_upper,
        v_lower
    )
    md_lines.extend(["", v_f, ""])

    # 4.5. Volatility Squeeze section
    if context_data is not None and "squeeze" in context_data:
        sq = context_data["squeeze"]
        if sq.get("status") == "ok":
            active_str = "Active" if sq["squeeze_active"] else "Not Active"
            md_lines.extend([
                "## 4.5. Volatility Squeeze",
                f"- **Squeeze Status:** `{active_str}`",
                f"- **Squeeze Value:** `{sq['squeeze_value']:.4f}`",
                f"- **Squeeze Duration:** `{sq['squeeze_duration']}` bar(s)",
                "",
                squeeze_finding(sq["squeeze_active"], sq["squeeze_duration"]),
                "",
            ])

    # 5. Support & Resistance section
    md_lines.extend([
        "## 5. Support & Resistance Levels",
    ])
    supports, resistances = [], []
    if "pivots" in levels_data:
        raw_supports = levels_data["pivots"].get("supports", [])
        raw_resistances = levels_data["pivots"].get("resistances", [])
        
        current_price = float(price_data.df["Close"].iloc[-1])
        all_levels = raw_supports + raw_resistances
        supports = [x for x in all_levels if x <= current_price]
        resistances = [x for x in all_levels if x > current_price]
        
        if supports:
            md_lines.append("- **Key Support Levels:** " + ", ".join(f"`{x:.2f}`" for x in sorted(list(set(supports)))))
        else:
            md_lines.append("- **Key Support Levels:** None detected")
            
        if resistances:
            md_lines.append("- **Key Resistance Levels:** " + ", ".join(f"`{x:.2f}`" for x in sorted(list(set(resistances)))))
        else:
            md_lines.append("- **Key Resistance Levels:** None detected")
            
    l_f = levels_finding(supports, resistances)
    md_lines.extend(["", l_f, ""])

    # 5.5. Volume Profile & Value Area section
    if context_data is not None and "volume_profile" in context_data:
        vp = context_data["volume_profile"]
        if vp.get("status") == "ok":
            md_lines.extend([
                "## 5.5. Volume Profile & Value Area",
                f"- **Point of Control (POC):** `{vp['poc']:.2f}`",
                f"- **Value Area High (VAH):** `{vp['vah']:.2f}`",
                f"- **Value Area Low (VAL):** `{vp['val']:.2f}`",
                f"- **Price vs Value Area:** `{vp['state']}` (Close vs `[{vp['val']:.2f}, {vp['vah']:.2f}]`)",
                "",
                volume_profile_finding(vp["state"], vp["poc"], vp["vah"], vp["val"]),
                "",
            ])

    # 5.6. Weekly Volume Profile & Value Area section
    if context_data is not None and "volume_profile_weekly" in context_data:
        vpw = context_data["volume_profile_weekly"]
        if vpw.get("status") == "ok":
            md_lines.extend([
                "## 5.6. Weekly Volume Profile & Value Area",
                f"- **Weekly Point of Control (POC):** `{vpw['poc_weekly']:.2f}`",
                f"- **Weekly Value Area High (VAH):** `{vpw['vah_weekly']:.2f}`",
                f"- **Weekly Value Area Low (VAL):** `{vpw['val_weekly']:.2f}`",
                f"- **Price vs Weekly Value Area:** `{vpw['state_weekly']}` (Close vs `[{vpw['val_weekly']:.2f}, {vpw['vah_weekly']:.2f}]`)",
                "",
                volume_profile_weekly_finding(vpw["state_weekly"], vpw["poc_weekly"], vpw["vah_weekly"], vpw["val_weekly"]),
                "",
            ])

    # 5.7. Fibonacci Retracement section
    if context_data is not None and "fibonacci" in context_data:
        fib = context_data["fibonacci"]
        if fib.get("status") in ("ok", "warning"):
            md_lines.extend([
                "## 5.7. Fibonacci Retracement Levels",
                f"- **Swing High (252-bar):** `{fib['swing_high']:.2f}`",
                f"- **Swing Low (252-bar):** `{fib['swing_low']:.2f}`",
                f"- **Swing Direction:** `{fib['direction']}`",
                "",
                "### Retracement Level Touch respect Statistics",
                "| Level | Price | Touches (n) | Historical Post-Touch Mean Return (10-bar) | Win Rate | Reliable? |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |",
            ])
            for lvl, pr in fib["levels"].items():
                st = fib["respect_stats"][lvl]
                rel_val = "Yes" if st["reliable"] else "No (n < 30)"
                md_lines.append(f"| {lvl:.3f} | {pr:.2f} | {st['n']} | {st['mean']:.4f} | {st['win_rate']:.2%} | {rel_val} |")
                
            md_lines.extend([
                "",
                fibonacci_finding(fib),
                "",
            ])

    # 5.8. Donchian Channels section
    if context_data is not None and "donchian" in context_data:
        don = context_data["donchian"]
        if don.get("status") in ("ok", "warning"):
            u20 = float(don["upper_20"].iloc[-1]) if hasattr(don["upper_20"], "iloc") else float(don["upper_20"])
            l20 = float(don["lower_20"].iloc[-1]) if hasattr(don["lower_20"], "iloc") else float(don["lower_20"])
            m20 = float(don["mid_20"].iloc[-1]) if hasattr(don["mid_20"], "iloc") else float(don["mid_20"])
            
            u55 = float(don["upper_55"].iloc[-1]) if hasattr(don["upper_55"], "iloc") else float(don["upper_55"])
            l55 = float(don["lower_55"].iloc[-1]) if hasattr(don["lower_55"], "iloc") else float(don["lower_55"])
            m55 = float(don["mid_55"].iloc[-1]) if hasattr(don["mid_55"], "iloc") else float(don["mid_55"])
            
            md_lines.extend([
                "## 5.8. Donchian Channels (20/55) & Breakouts",
                f"- **20-day Channel Position:** `{don['pos_pct_20']:.1f}%` (Upper: `{u20:.2f}`, Lower: `{l20:.2f}`, Mid: `{m20:.2f}`)",
                f"- **55-day Channel Position:** `{don['pos_pct_55']:.1f}%` (Upper: `{u55:.2f}`, Lower: `{l55:.2f}`, Mid: `{m55:.2f}`)",
                "",
                donchian_finding(don["pos_pct_20"], don["pos_pct_55"], don.get("breakout_desc")),
                "",
            ])

    # 5.9. Candlestick Patterns section
    if context_data is not None and "candles" in context_data:
        cnd = context_data["candles"]
        if cnd.get("status") == "ok":
            md_lines.extend([
                "## 5.9. Candlestick Patterns",
                "| Pattern | Status Today | Direction |",
                "| :--- | :--- | :--- |",
            ])
            dirs = {
                "doji": "Neutral",
                "hammer": "Bullish Reversal",
                "shooting_star": "Bearish Reversal",
                "bullish_engulfing": "Bullish Reversal",
                "bearish_engulfing": "Bearish Reversal",
            }
            for pat_name, series in cnd["patterns"].items():
                active_val = "Active" if series.iloc[-1] else "Inactive"
                name = pat_name.replace("_", " ").title()
                md_lines.append(f"| {name} | {active_val} | {dirs[pat_name]} |")
                
            md_lines.extend([
                "",
                candles_finding({k: v.iloc[-1] for k, v in cnd["patterns"].items()}),
                "",
            ])

    # 6. Context & regime section
    if context_data is not None:
        md_lines.append("## 6. Context & Regime")
        md_lines.append(
            f"- **Trend Regime (ADX):** `{context_data.get('trend_regime', 'undetermined')}` "
            f"(ADX: `{context_data.get('last_adx', float('nan')):.2f}`)"
        )
        md_lines.append(
            f"- **Volatility Regime (ATR%):** `{context_data.get('volatility_regime', 'unknown')}` "
            f"(ATR: `{context_data.get('last_atr', float('nan')):.2f}`)"
        )
        div = context_data.get("divergence", {}) or {}
        if div.get("bearish") or div.get("bullish"):
            md_lines.append(f"- **Price/RSI Divergence:** `{div.get('detail', '')}`")
        else:
            md_lines.append("- **Price/RSI Divergence:** None detected")
        md_lines.append(
            "- *Context describes the regime; read the indicators above through it "
            "(e.g. an overbought RSI behaves differently in a strong trend vs a range).*"
        )
        
        c_f = context_finding(
            context_data.get('trend_regime', 'undetermined'),
            float(context_data.get('last_adx', float('nan'))),
            context_data.get('volatility_regime', 'unknown'),
            float(context_data.get('last_atr', float('nan'))),
            div.get('detail', '')
        )
        md_lines.extend(["", c_f, ""])

    # 6.5. Base Rates
    if context_data is not None and "baserates_stats" in context_data:
        stats_list = context_data["baserates_stats"]
        md_lines.append("## 6.5. Empirical Base Rates (Conditional Historical Distributions)")
        md_lines.append("> [!WARNING]")
        md_lines.append("> **Descriptive Statistics Warning:** Base rates are strictly descriptive over this asset's historical data. Markets are non-stationary, past patterns do not guarantee future returns, and sample sizes may be small. This is not a forecast.")
        md_lines.append("")
        md_lines.append("| Horizon | Condition | Sample Size (N) | Win Rate (%) | Mean Return (%) | Median Return (%) | Reliable? |")
        md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for row in stats_list:
            horizon = row["horizon"]
            cond_name = row["condition"]
            n = row["n"]
            wr = f"{row['win_rate']*100:.2f}%" if not np.isnan(row['win_rate']) else "N/A"
            mr = f"{row['mean']*100:.2f}%" if not np.isnan(row['mean']) else "N/A"
            med = f"{row['median']*100:.2f}%" if not np.isnan(row['median']) else "N/A"
            reliable_str = "Yes" if row["reliable"] else "No"
            md_lines.append(f"| {horizon}d | {cond_name} | {n} | {wr} | {mr} | {med} | {reliable_str} |")
        md_lines.append("")

    # 6.6. Relative Strength
    if context_data is not None and "relative" in context_data and context_data["relative"] is not None:
        rel = context_data["relative"]
        md_lines.append("## 6.6. Relative Strength vs Benchmark")
        md_lines.append(f"- **Benchmark Ticker:** `{rel['benchmark_ticker']}`")
        md_lines.append(f"- **Current State:** `{rel['state']}`")
        md_lines.append(f"- **Last RS Ratio:** `{rel['rs'].iloc[-1]:.6f}` (vs SMA: `{rel['rs_ma'].iloc[-1]:.6f}`)")
        
        rel_f = relative_finding(
            rel['benchmark_ticker'],
            rel['state'],
            float(rel['rs'].iloc[-1]),
            float(rel['rs_ma'].iloc[-1])
        )
        md_lines.extend(["", rel_f, ""])

    # 6.7. Seasonality
    if context_data is not None and context_data.get("seasonality_summary") is not None:
        seas_sum = context_data["seasonality_summary"]
        seas_table = context_data.get("seasonality_table")
        md_lines.append("## 6.7. Monthly Seasonality Summary")
        md_lines.append("> [!NOTE]")
        md_lines.append("> **Historical Seasonality Warning:** Seasonality is strictly historical and descriptive over the asset's calendar months. Markets are non-stationary and past performance does not guarantee future results.")
        md_lines.append("> Low sample size (e.g. N < 5 indicated by ⚠️) suggests the estimates have high variance and are less statistically reliable.")
        md_lines.append("")
        md_lines.append("| Month | Average Return (%) | Win Rate (%) | Sample Size (N) |")
        md_lines.append("| :--- | :--- | :--- | :--- |")
        col_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for m in range(1, 13):
            m_name = col_names[m-1]
            if m in seas_sum.index:
                row = seas_sum.loc[m]
                avg_ret = f"{row['mean']*100:.2f}%" if not np.isnan(row['mean']) else "N/A"
                win_r = f"{row['win_rate']*100:.2f}%" if not np.isnan(row['win_rate']) else "N/A"
                
                n_val = None
                if seas_table is not None and hasattr(seas_table, "columns") and m in seas_table.columns:
                    n_val = int(seas_table[m].notna().sum())
                elif "n" in row and not np.isnan(row["n"]):
                    n_val = int(row["n"])
                    
                if n_val is not None:
                    n_str = f"{n_val} ⚠️" if n_val < 5 else f"{n_val}"
                else:
                    n_str = "N/A"
            else:
                avg_ret, win_r, n_str = "N/A", "N/A", "N/A"
            md_lines.append(f"| {m_name} | {avg_ret} | {win_r} | {n_str} |")
        
        if seas_sum is not None and not seas_sum.empty:
            valid_seas = seas_sum.dropna(subset=["mean"])
            if not valid_seas.empty:
                best_idx = valid_seas["mean"].idxmax()
                best_row = valid_seas.loc[best_idx]
                best_month_name = col_names[best_idx - 1]
                best_month_ret = float(best_row["mean"])
                best_month_wr = float(best_row["win_rate"])
            else:
                best_month_name, best_month_ret, best_month_wr = "N/A", float('nan'), float('nan')
        else:
            best_month_name, best_month_ret, best_month_wr = "N/A", float('nan'), float('nan')
            
        seas_f = seasonality_finding(best_month_name, best_month_ret, best_month_wr)
        md_lines.extend(["", seas_f, ""])

    # 6.8. Volume Analysis
    if context_data is not None and context_data.get("volume") is not None:
        vol = context_data["volume"]
        md_lines.append("## 6.8. Volume Analysis (OBV & VWAP)")
        md_lines.append("> [!NOTE]")
        md_lines.append("> **VWAP Approximation Notice:** VWAP calculations are daily-bar approximations (anchored daily VWAP) and not true intraday VWAP. Volume metrics are only as reliable as the underlying reporting data quality.")
        md_lines.append("")
        md_lines.append(f"- **OBV Trend / Divergence:** `{vol['divergence']['state']}` (Price slope: `{vol['divergence']['price_slope']:.6f}`, OBV slope: `{vol['divergence']['obv_slope']:.6f}`)")
        md_lines.append(f"- **VWAP (20) State:** `{vol['state']['state']}` (Distance: `{vol['state']['distance_pct']:.2f}%`) [Approximation: Anchored Daily VWAP]")
        
        mfi_val = vol.get("mfi_value", float("nan"))
        mfi_lbl = vol.get("mfi_state", "neutral")
        md_lines.append(f"- **MFI (14) value:** `{mfi_val:.2f}` (State: `{mfi_lbl}`)")
        
        avwap = vol.get("anchored_vwap", {})
        if avwap:
            md_lines.extend([
                f"- **Anchored VWAP YTD:** `{avwap.get('ytd_val', float('nan')):.2f}` (State: `{avwap.get('ytd_state', 'unknown')}`)",
                f"- **Anchored VWAP 52w High:** `{avwap.get('high_val', float('nan')):.2f}` (State: `{avwap.get('high_state', 'unknown')}`)",
                f"- **Anchored VWAP 52w Low:** `{avwap.get('low_val', float('nan')):.2f}` (State: `{avwap.get('low_state', 'unknown')}`)",
            ])
            
        vol_f = volume_finding(
            vol['divergence']['state'],
            float(vol['divergence']['price_slope']),
            float(vol['divergence']['obv_slope']),
            vol['state']['state'],
            float(vol['state']['distance_pct']),
            mfi_val,
            mfi_lbl,
            avwap.get('ytd_state'),
            avwap.get('high_state'),
            avwap.get('low_state'),
        )
        md_lines.extend(["", vol_f, ""])

    # 6.9 & 6.10 Econometric Analysis
    if context_data is not None and context_data.get("econometrics") is not None:
        econ = context_data["econometrics"]
        if econ.get("status") == "ok":
            acf_p = econ["acf_pacf"]
            dist = econ["distribution"]
            
            md_lines.append("## 6.9. Predictability Analysis (ACF/PACF)")
            md_lines.append("> [!WARNING]")
            md_lines.append("> **Statistical Analysis Notice:** These results are strictly descriptive over this asset's historical returns. Markets are non-stationary; this is not a forecast.")
            md_lines.append("")
            
            # Use the module's early-lag finding (same multiple-comparison
            # discipline as the volatility-clustering flag) instead of listing
            # every lag that crosses the band over the full 40-lag scan.
            if acf_p.get("raw_autocorrelation_detected"):
                lags_str = ", ".join(map(str, acf_p.get("raw_significant_early_lags", [])))
                md_lines.append(f"- **Raw Returns Autocorrelation:** significant autocorrelation at early lag(s) {lags_str} (a finding, not a trading signal)")
            else:
                md_lines.append("- **Raw Returns Autocorrelation:** no significant autocorrelation at early lags (consistent with a random walk)")
                
            if acf_p["volatility_clustering_detected"]:
                md_lines.append("- **Volatility Clustering:** volatility clustering detected (ARCH-type effects): calm and turbulent periods cluster")
            else:
                md_lines.append("- **Volatility Clustering:** no clustering")
                
            if "ljung_box" in econ:
                lb = econ["ljung_box"]
                sig_str = "significant" if lb["significant"] else "no"
                md_lines.append(f"- **Ljung-Box Joint Test:** Q({lb['lags']}) = `{lb['lb_stat']:.4f}` (p = `{lb['lb_pvalue']:.4f}`): {sig_str} joint autocorrelation up to lag {lb['lags']}.")
            md_lines.append("")
            
            md_lines.append("## 6.10. Return Distribution Analysis")
            md_lines.append("> [!WARNING]")
            md_lines.append("> **Statistical Analysis Notice:** These results are strictly descriptive over this asset's historical returns. Markets are non-stationary; this is not a forecast.")
            md_lines.append("")
            
            skew_val = dist["skew"]
            skew_desc = "positively skewed (right-tailed)" if skew_val > 0.05 else "negatively skewed (left-tailed)" if skew_val < -0.05 else "approximately symmetric"
            if "dist_uncertainty" in econ:
                dist_unc = econ["dist_uncertainty"]
                skew_ci_str = f" (95% bootstrap CI [{dist_unc['skew_ci'][0]:.4f}, {dist_unc['skew_ci'][1]:.4f}])"
            else:
                skew_ci_str = ""
            md_lines.append(f"- **Skewness:** `{skew_val:.4f}`{skew_ci_str} ({skew_desc})")
            
            kurt_val = dist["excess_kurtosis"]
            kurt_desc = f"excess kurtosis = {kurt_val:.2f} (fat-tailed: extreme moves more frequent than a Normal distribution predicts)" if kurt_val > 0.5 else f"excess kurtosis = {kurt_val:.2f} (thin-tailed)" if kurt_val < -0.5 else f"excess kurtosis = {kurt_val:.2f} (mesokurtic)"
            if "dist_uncertainty" in econ:
                dist_unc = econ["dist_uncertainty"]
                kurt_ci_str = f" (95% bootstrap CI [{dist_unc['kurtosis_ci'][0]:.4f}, {dist_unc['kurtosis_ci'][1]:.4f}], n_boot={dist_unc['n_boot']})"
            else:
                kurt_ci_str = ""
            md_lines.append(f"- **Excess Kurtosis:** {kurt_desc}{kurt_ci_str}")
            
            jb_stat = dist["jb_stat"]
            jb_p = dist["jb_pvalue"]
            if dist["is_normal"]:
                md_lines.append(f"- **Normality Check (Jarque-Bera):** returns are consistent with a Normal distribution (p = {jb_p:.4f}, stat = {jb_stat:.2f})")
            else:
                md_lines.append(f"- **Normality Check (Jarque-Bera):** returns are not consistent with a Normal distribution (p = {jb_p:.4f}, stat = {jb_stat:.2f})")
            md_lines.append("")

    # 6.11 - 6.14 Risk Analysis
    if context_data is not None and context_data.get("risk") is not None:
        risk = context_data["risk"]
        if risk.get("status") == "ok":
            r52 = risk["52week"]
            dd_series = risk["drawdown_series"]
            episodes = risk["drawdown_episodes"]
            liq = risk["liquidity"]
            beta_d = risk["beta"]
            
            # 6.11
            md_lines.append("## 6.11. 52-Week Range Position")
            md_lines.append(f"- **52-Week High:** `{r52['high']:.2f}`")
            md_lines.append(f"- **52-Week Low:** `{r52['low']:.2f}`")
            md_lines.append(f"- **Current Close:** `{r52['current']:.2f}`")
            r52_pct = f"{r52['position_pct']:.1f}%" if not np.isnan(r52['position_pct']) else "N/A"
            md_lines.append(f"- **Range Position:** {r52_pct} (classified as `{r52['state']}`)")
            md_lines.append("")
            
            # 6.12
            md_lines.append("## 6.12. Drawdown History")
            curr_dd = dd_series["drawdown"].iloc[-1]
            if curr_dd == 0:
                dd_state_str = "at all-time high"
            else:
                peak_idx = dd_series[dd_series["close"] == dd_series["running_max"]].index
                peak_date_str = peak_idx[-1].strftime("%Y-%m-%d") if len(peak_idx) > 0 else "unknown"
                dd_state_str = f"currently in drawdown of {abs(curr_dd)*100.0:.2f}% from peak on {peak_date_str}"
            md_lines.append(f"- **Current Status:** {dd_state_str}")
            md_lines.append("")
            md_lines.append("| Rank | Peak Date | Trough Date | Recovery Date | Trough Drawdown (%) | Days to Recover |")
            md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for idx, ep in enumerate(episodes):
                rec_date = ep["recovery_date"] if ep["recovery_date"] is not None else "not yet recovered"
                days = str(ep["days_to_recover"]) if ep["days_to_recover"] is not None else "N/A"
                md_lines.append(f"| #{idx+1} | {ep['peak_date']} | {ep['trough_date']} | {rec_date} | {ep['trough_pct']*100.0:.2f}% | {days} |")
            md_lines.append("")
            
            # 6.13
            md_lines.append("## 6.13. Liquidity Assessment")
            md_lines.append(f"- **Average 20-Day Traded Volume:** `{liq['adv20']:,.0f}`")
            md_lines.append(f"- **Average 90-Day Traded Volume:** `{liq['adv90']:,.0f}`")
            md_lines.append(f"- **Average 20-Day Traded Value:** `{liq['avg_value_20']:,.2f}` (quote currency)")
            md_lines.append(f"- **Liquidity State:** `{liq['state']}` (thresholds: high ≥ 50M, low < 5M)")
            md_lines.append("> [!NOTE]")
            md_lines.append("> **Liquidity Notice:** Traded values are denominated in the asset's quote currency (e.g. USD for US stocks, TRY for BIST). Larger positions in low-liquidity assets may face significant price impact upon entry or exit.")
            md_lines.append("")
            
            # 6.14
            if not np.isnan(beta_d["beta"]):
                md_lines.append("## 6.14. Systematic Risk (Beta)")
                md_lines.append("> [!WARNING]")
                md_lines.append("> **Systematic Risk Warning:** Beta and regression statistics are strictly historical and descriptive over the overlapping sample returns. Markets are non-stationary; this is not a forecast.")
                md_lines.append("")
                md_lines.append(f"- **Beta vs SPY:** `{beta_d['beta']:.2f}` (classified as `{beta_d['state']}`)")
                md_lines.append(f"- **Annualized Alpha:** `{beta_d['alpha_annualized']*100.0:.2f}%` (vs SPY benchmark)")
                md_lines.append(f"- **R-Squared (R²):** `{beta_d['r_squared']:.4f}`")
                md_lines.append(f"- **Overlapping Bars (N):** {beta_d['n']}")
                
                risk_f = risk_finding(
                    r52['state'],
                    float(dd_series["drawdown"].iloc[-1]) * 100.0,
                    liq['state'],
                    float(beta_d['beta']),
                    beta_d['state']
                )
                md_lines.extend(["", risk_f, ""])

    # 6.15. Score Profile
    if context_data is not None and context_data.get("scores") is not None:
        scores_dict = context_data["scores"]
        md_lines.append("## 6.15. Score Profile (Independent Dimensions)")
        md_lines.append("> [!NOTE]")
        md_lines.append("> **Multi-Dimensional Score Notice:** These scores are computed deterministically based on static rules. No overall or combined composite score is provided to avoid making implicit trading recommendations.")
        md_lines.append("")
        md_lines.append("| Dimension | Score (0-100) | State Label | Details / Rule Breakdown |")
        md_lines.append("| :--- | :--- | :--- | :--- |")
        for dim, info in scores_dict.items():
            name = dim.replace("_", " ").title()
            val = info["value"]
            state = info["state_label"]
            breakdown = "; ".join(info["rule_breakdown"])
            
            note = info.get("description_note", "")
            if note:
                breakdown += f" (*Note: {note}*)"
                
            md_lines.append(f"| {name} | {val} | {state} | {breakdown} |")
        
        sc_f = scores_finding(
            scores_dict.get("trend_strength", {}).get("value", 0),
            scores_dict.get("momentum", {}).get("value", 0),
            scores_dict.get("trend_maturity", {}).get("value", 0),
            scores_dict.get("liquidity", {}).get("value", 0),
            scores_dict.get("volatility_level", {}).get("value", 0),
            scores_dict.get("statistical_edge", {}).get("value", 0)
        )
        md_lines.extend(["", sc_f, ""])

    # 6.16. Stationarity Analysis
    if context_data is not None and context_data.get("econometrics") is not None:
        econ = context_data["econometrics"]
        if "stationarity_levels" in econ and "stationarity_returns" in econ:
            sl = econ["stationarity_levels"]
            sr = econ["stationarity_returns"]
            
            md_lines.append("## 6.16. Stationarity Analysis")
            md_lines.append("> [!NOTE]")
            md_lines.append("> **Stationarity Notice:** Stationarity is a key assumption for many statistical models. Level prices are typically non-stationary (random walks), while log returns should be stationary for model validity.")
            md_lines.append("")
            md_lines.append("| Series | ADF Stat | ADF p-value | ADF Decision | KPSS Stat | KPSS p-value | KPSS Decision | Combined Verdict |")
            md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            md_lines.append(f"| Price Levels ({config.STATIONARITY_REG_LEVELS}) | `{sl['adf']['stat']:.4f}` | `{sl['adf']['pvalue']:.4f}` | {sl['adf']['decision']} | `{sl['kpss']['stat']:.4f}` | `{sl['kpss']['pvalue']:.4f}` | {sl['kpss']['decision']} | **{sl['state_label']}** |")
            md_lines.append(f"| Log Returns ({config.STATIONARITY_REG_RETURNS}) | `{sr['adf']['stat']:.4f}` | `{sr['adf']['pvalue']:.4f}` | {sr['adf']['decision']} | `{sr['kpss']['stat']:.4f}` | `{sr['kpss']['pvalue']:.4f}` | {sr['kpss']['decision']} | **{sr['state_label']}** |")
            md_lines.append("")
            
            md_lines.append("### Findings & Implications")
            if sl["state_label"] == "non-stationary (unit root / random walk)" and sr["state_label"] == "stationary":
                md_lines.append("Price levels are non-stationary (random walk) as expected; log returns are stationary, confirming returns are suitable for statistical modeling.")
            else:
                md_lines.append(f"Price levels are classified as **{sl['state_label']}** and log returns as **{sr['state_label']}**.")
            md_lines.append("")

    # 6.17. Structural Break Analysis
    if context_data is not None and context_data.get("econometrics") is not None:
        econ = context_data["econometrics"]
        if "cusum" in econ and "breaks" in econ:
            cusum = econ["cusum"]
            breaks_list = econ["breaks"]
            
            md_lines.append("## 6.17. Structural Break Analysis")
            if cusum["unstable"] or len(breaks_list) > 0:
                md_lines.append("> [!WARNING]")
                md_lines.append("> **Data-Quality / Interpretation Notice (Meta-Warning):** A structural regime break (mean or volatility shift) was detected in the time series. Older data may not represent the current market regime, so statistics and risk metrics computed over the full history may under- or mis-state current risk characteristics. This is a descriptive data-quality caveat, not a trading signal.")
            else:
                md_lines.append("> [!NOTE]")
                md_lines.append("> **Structural Break Notice:** Parameter stability is maintained; no significant structural shifts were detected in the return series.")
            md_lines.append("")
            
            md_lines.append(f"- **OLS Residuals CUSUM Test:** Stat: `{cusum['stat']:.4f}`, p-value: `{cusum['pvalue']:.4f}` (Stability: {'**UNSTABLE**' if cusum['unstable'] else 'STABLE'})")
            md_lines.append(f"- **Number of Detected Breaks:** `{len(breaks_list)}` (max allowed: {config.BREAK_MAX})")
            md_lines.append("")
            
            if len(breaks_list) > 0:
                md_lines.append("| Break Date | Index | Shift Type | Mean (Before / After) | Variance (Before / After) | LR Stat |")
                md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
                for b in breaks_list:
                    md_lines.append(f"| {b['date']} | {b['index']} | `{b['type']}` | `{b['mean_before']:.6f}` / `{b['mean_after']:.6f}` | `{b['var_before']:.8f}` / `{b['var_after']:.8f}` | `{b['lr']:.2f}` |")
                md_lines.append("")
                
                for b in breaks_list:
                    if b["type"] == "volatility_shift":
                        md_lines.append(f"A volatility regime shift was detected around {b['date']}. Statistics computed over the full history may understate current risk characteristics.")
                    elif b["type"] == "mean_shift":
                        md_lines.append(f"A mean returns shift was detected around {b['date']}, indicating a major change in price drift characteristics.")
                    elif b["type"] == "both":
                        md_lines.append(f"A structural break with both mean and volatility shifts was detected around {b['date']}.")
                md_lines.append("")
                
            if "regime_conditional" in econ:
                rc = econ["regime_conditional"]
                md_lines.append("### Current Regime vs Full Sample Analysis")
                if rc["regime_too_short"]:
                    md_lines.append("> [!WARNING]")
                    md_lines.append(f"> **Low Sample Warning:** The current post-break regime sample is small (n={rc['n_regime']}); statistical estimates may be noisy.")
                    md_lines.append("")
                
                md_lines.append(f"| Statistic | Full Sample (n={rc['n_full']}) | Current Regime since {rc['regime_start']} (n={rc['n_regime']}) |")
                md_lines.append("| :--- | :--- | :--- |")
                md_lines.append(f"| Annualized Volatility | `{rc['full']['ann_vol']*100:.2f}%` | `{rc['regime']['ann_vol']*100:.2f}%` |")
                md_lines.append(f"| Excess Kurtosis | `{rc['full']['excess_kurtosis']:.4f}` | `{rc['regime']['excess_kurtosis']:.4f}` |")
                md_lines.append(f"| Skewness | `{rc['full']['skew']:.4f}` | `{rc['regime']['skew']:.4f}` |")
                md_lines.append("")
                
                if rc["is_split"]:
                    turb_desc = "more" if rc["regime"]["ann_vol"] > rc["full"]["ann_vol"] else "less"
                    md_lines.append(f"Since the last regime break on {rc['regime_start']}, annualized volatility is `{rc['regime']['ann_vol']*100:.2f}%` vs `{rc['full']['ann_vol']*100:.2f}%` over the full history; the current regime is {turb_desc} turbulent. Full-history statistics may under/over-state current characteristics.")
                else:
                    md_lines.append("No regime break was detected; the current regime statistics are identical to the full-history sample.")
                md_lines.append("")

    # 6.18. Long Memory Analysis (Hurst Exponent)
    if context_data is not None and context_data.get("econometrics") is not None:
        econ = context_data["econometrics"]
        if "hurst" in econ and econ["hurst"] is not None:
            ret_h = econ["hurst"]["returns"]
            vol_h = econ["hurst"]["volatility"]
            
            md_lines.append("## 6.18. Long Memory Analysis (Hurst Exponent)")
            md_lines.append("> [!NOTE]")
            md_lines.append("> **Long Memory Notice:** The rescaled range (R/S) Hurst exponent measures long-term memory in time series. H = 0.5 implies a random walk, H > 0.55 indicates persistence (trending), and H < 0.45 indicates anti-persistence (mean-reverting). In short samples, R/S estimation may exhibit a slight upward bias.")
            md_lines.append("")
            md_lines.append(f"- **Returns Hurst Exponent (H):** `{ret_h['hurst']:.4f}` (classified as `{ret_h['state_label']}`)")
            md_lines.append(f"- **Volatility Hurst Exponent (H_vol):** `{vol_h['hurst']:.4f}` (classified as `{vol_h['state_label']}`)")
            md_lines.append("")
            
            md_lines.append("### Findings & Implications")
            md_lines.append(
                f"Returns show H = {ret_h['hurst']:.2f} (classified as {ret_h['state_label']}), "
                f"while squared returns (volatility) show H = {vol_h['hurst']:.2f} (classified as {vol_h['state_label']})."
            )
            if vol_h["hurst"] > 0.50:
                md_lines.append(" The high Hurst exponent in volatility indicates strong volatility persistence (long memory in risk shocks).")
            md_lines.append("")

    # 6.19. Conditional Beta (Quantile Regression)
    if context_data is not None and context_data.get("econometrics") is not None:
        econ = context_data["econometrics"]
        if "quantile_beta" in econ and econ["quantile_beta"] is not None:
            qb = econ["quantile_beta"]
            
            md_lines.append("## 6.19. Conditional Beta (Quantile Regression)")
            md_lines.append("> [!NOTE]")
            md_lines.append("> **Conditional Beta Notice:** Quantile regression estimates the slope (beta) of the conditional quantiles of stock returns given the benchmark returns. This reveals whether market co-movement is asymmetric in the tails of the distribution. OLS beta is shown for comparison.")
            md_lines.append("")
            if qb["state_label"] == "symmetric_beta":
                md_lines.append(f"- **Asymmetry Classification:** `{qb['state_label']}`")
            elif qb.get("asymmetry_significant"):
                md_lines.append(
                    f"- **Asymmetry Classification:** `{qb['state_label']}` "
                    f"(tail CIs do not overlap — statistically significant)"
                )
            else:
                md_lines.append(
                    f"- **Asymmetry Classification:** `{qb['state_label']}` "
                    f"(point-estimate finding only: the tail confidence intervals overlap, "
                    f"so the asymmetry is not statistically significant)"
                )
            md_lines.append(f"- **OLS Reference Beta:** `{qb['ols_beta']:.4f}`")
            md_lines.append("")
            
            md_lines.append("| Quantile (tau) | Beta Coefficient | 95% Confidence Interval |")
            md_lines.append("| :--- | :--- | :--- |")
            for q in qb["quantiles"]:
                val = qb["betas"][q]
                ci_l, ci_h = qb["cis"][q]
                md_lines.append(f"| `{q:.2f}` | `{val:.4f}` | `[{ci_l:.4f}, {ci_h:.4f}]` |")
            md_lines.append("")
            
            md_lines.append("### Findings & Implications")
            q_low = min(qb["quantiles"])
            q_high = max(qb["quantiles"])
            beta_low = qb["betas"][q_low]
            beta_high = qb["betas"][q_high]
            
            if qb["state_label"] == "downside_sensitive":
                md_lines.append(
                    f"The OLS beta is {qb['ols_beta']:.2f}, but the conditional beta in the adverse tail (tau = {q_low:.2f}) "
                    f"is {beta_low:.2f} vs {beta_high:.2f} in the favorable tail (tau = {q_high:.2f}). "
                    f"This asset's adverse-tail outcomes co-move more strongly with the market than its favorable-tail outcomes (downside-sensitive). "
                    f"An average OLS beta understates co-movement risk during extreme market declines."
                )
            elif qb["state_label"] == "upside_sensitive":
                md_lines.append(
                    f"The OLS beta is {qb['ols_beta']:.2f}, but the conditional beta in the adverse tail (tau = {q_low:.2f}) "
                    f"is {beta_low:.2f} vs {beta_high:.2f} in the favorable tail (tau = {q_high:.2f}). "
                    f"This asset's favorable-tail outcomes co-move more strongly with the market than its adverse-tail outcomes (upside-sensitive)."
                )
            else:
                md_lines.append(
                    f"The conditional beta values across all quantiles (varying from {beta_low:.2f} to {beta_high:.2f}) "
                    f"are relatively close to the OLS beta of {qb['ols_beta']:.2f}. "
                    f"This asset's market co-movement is classified as symmetric across different return regimes."
                )
            md_lines.append("")

    # 6.20. Variance Ratio (Lo-MacKinlay)
    if context_data is not None and context_data.get("econometrics") is not None:
        econ = context_data["econometrics"]
        if "variance_ratio" in econ and econ["variance_ratio"] is not None:
            vr_data = econ["variance_ratio"]
            
            md_lines.append("## 6.20. Variance Ratio (Lo-MacKinlay)")
            md_lines.append("> [!NOTE]")
            md_lines.append("> **Variance Ratio Notice:** The Variance Ratio test evaluates the Random Walk Hypothesis by comparing the variance of q-period returns to q times the variance of 1-period returns. We use the **overlapping** window type with heteroskedasticity-robust standard errors (M2 statistic) under the null of a random walk. This is a descriptive historical statistic, not a trading signal.")
            md_lines.append("")
            md_lines.append(f"- **Primary Joint Verdict (Lowest q):** `{vr_data['state_label']}` (window type: `{vr_data['window']}`)")
            md_lines.append("")
            
            md_lines.append("| q (Period) | Variance Ratio (VR) | z-statistic (M2) | p-value | Verdict |")
            md_lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for q in vr_data["q_values"]:
                vr_val = vr_data["vr"][q]
                z_val = vr_data["zstat"][q]
                p_val = vr_data["pvalue"][q]
                
                if abs(z_val) < 1.96:
                    verd = "random walk"
                elif vr_val > 1.0:
                    verd = "trending (positive autocorr)"
                else:
                    verd = "mean-reverting"
                    
                md_lines.append(f"| `{q}` | `{vr_val:.4f}` | `{z_val:.4f}` | `{p_val:.4f}` | `{verd}` |")
            
            e_f = econometrics_finding(
                econ.get("stationarity_returns", {}).get("state_label", "unknown"),
                econ.get("ljung_box", {}).get("significant", False),
                len(econ.get("breaks", [])),
                vr_data["state_label"]
            )
            md_lines.extend(["", e_f, ""])

    # 7. Charts
    drawn = [(caption, path) for caption, path in charts if path.exists()]
    if drawn:
        md_lines.append("## 7. Technical Charts")
        for caption, path in drawn:
            md_lines.append(f"**{caption}**")
            md_lines.append("")
            md_lines.append(f"![{caption}]({path.name})")
            md_lines.append("")
            
    if context_data is not None and context_data.get("briefing") is not None:
        md_lines.append("## 8. Analyst Briefing (Synthesis — Not Advice)")
        md_lines.append(context_data["briefing"])
        md_lines.append("")
        
    with report_file.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(md_lines))
        
    return str(report_file)


def print_terminal_summary(
    ticker: str,
    price_data: dl.PriceData,
    trend_data: Dict[str, Any],
    momentum_data: Dict[str, Any],
    volatility_data: Dict[str, Any],
    levels_data: Dict[str, Any],
    context_data: Dict[str, Any] | None = None,
    console: Console | None = None,
) -> None:
    """Print a beautiful summary table of all indicator states using Rich."""
    console = console or Console()
    
    table = Table(title=f"Techna Summary Dashboard · {ticker.upper()}", show_header=True, header_style="bold magenta")
    table.add_column("Indicator / Category", style="cyan")
    table.add_column("Metric / Value", justify="right")
    table.add_column("State / Status", style="green")
    
    # Price
    last_close = price_data.df["Close"].iloc[-1]
    table.add_row("Last Close Price", f"{last_close:.2f}", "Ok")
    
    # Trend
    t_state = trend_data.get("state", "sideways")
    t_color = "green" if t_state == "uptrend" else "red" if t_state == "downtrend" else "yellow"
    table.add_row("Trend State", "Price vs SMA50/SMA200", f"[{t_color}]{t_state}[/{t_color}]")
    
    # Weekly Trend & Align
    if context_data is not None and "mtf" in context_data:
        mtf_data = context_data["mtf"]
        if mtf_data.get("status") == "ok":
            w_trend = mtf_data["weekly_trend_state"]
            w_align = mtf_data["alignment"]
            align_color = "green" if w_align == "aligned_bullish" else "red" if w_align == "aligned_bearish" else "yellow"
            table.add_row("Weekly Trend & Align", f"Trend: {w_trend}", f"[{align_color}]{w_align}[/{align_color}]")
    
    # RSI
    rsi_val = momentum_data.get("last_rsi", float("nan"))
    rsi_st = momentum_data.get("rsi_state", "neutral")
    r_color = "red" if rsi_st == "overbought" else "green" if rsi_st == "oversold" else "white"
    table.add_row("RSI (14)", f"{rsi_val:.2f}", f"[{r_color}]{rsi_st}[/{r_color}]")
    
    # MACD
    m_state = momentum_data.get("macd_state", "bearish")
    m_color = "green" if m_state == "bullish" else "red"
    table.add_row("MACD State", "Hist: " + f"{momentum_data.get('last_macd', [0,0,0])[2]:.4f}", f"[{m_color}]{m_state}[/{m_color}]")
    
    # Bollinger Bands
    b_state = volatility_data.get("state", "within_bands")
    b_color = "red" if b_state == "above_upper" else "green" if b_state == "below_lower" else "white"
    table.add_row("Bollinger Bands", f"%B: {volatility_data.get('last_bands', [0,0,0,0,0])[3]:.4f}", f"[{b_color}]{b_state}[/{b_color}]")

    # Context & regime rows
    if context_data is not None:
        t_reg = context_data.get("trend_regime", "undetermined")
        tr_color = "green" if t_reg == "trending_up" else "red" if t_reg == "trending_down" else "yellow"
        table.add_row("Trend Regime (ADX)", f"ADX: {context_data.get('last_adx', float('nan')):.1f}", f"[{tr_color}]{t_reg}[/{tr_color}]")

        v_reg = context_data.get("volatility_regime", "unknown")
        table.add_row("Volatility Regime", f"ATR: {context_data.get('last_atr', float('nan')):.2f}", v_reg)

        div = context_data.get("divergence", {}) or {}
        if div.get("bearish"):
            div_txt, div_color = "bearish", "red"
        elif div.get("bullish"):
            div_txt, div_color = "bullish", "green"
        else:
            div_txt, div_color = "none", "white"
        table.add_row("Price/RSI Divergence", "swing compare", f"[{div_color}]{div_txt}[/{div_color}]")

        rel = context_data.get("relative")
        if rel is not None:
            r_st = rel.get("state", "neutral")
            r_color = "green" if r_st == "outperforming" else "red" if r_st == "underperforming" else "white"
            table.add_row("Relative Strength", f"vs {rel['benchmark_ticker']}", f"[{r_color}]{r_st}[/{r_color}]")

        vol = context_data.get("volume")
        if vol is not None:
            obv_div = vol.get("divergence", {})
            obv_st = obv_div.get("state", "neutral")
            obv_color = "green" if obv_st == "bullish_divergence" else "red" if obv_st == "bearish_divergence" else "white"
            table.add_row("OBV Divergence", f"slope: {obv_div.get('obv_slope', 0.0):.4f}", f"[{obv_color}]{obv_st}[/{obv_color}]")
            
            vwap_st = vol.get("state", {})
            vw_state = vwap_st.get("state", "unknown")
            vw_color = "green" if vw_state == "above_vwap" else "red" if vw_state == "below_vwap" else "white"
            table.add_row("Price vs VWAP", f"dist: {vwap_st.get('distance_pct', 0.0):.2f}%", f"[{vw_color}]{vw_state}[/{vw_color}]")

        econ = context_data.get("econometrics")
        if econ is not None and econ.get("status") == "ok":
            acf_p = econ["acf_pacf"]
            dist = econ["distribution"]
            
            clust_val = acf_p["volatility_clustering_detected"]
            clust_txt = "detected" if clust_val else "none"
            clust_color = "red" if clust_val else "green"
            table.add_row("Vol. Clustering", "ARCH effects", f"[{clust_color}]{clust_txt}[/{clust_color}]")
            
            norm_val = dist["is_normal"]
            norm_txt = "normal" if norm_val else "non-normal"
            norm_color = "green" if norm_val else "red"
            table.add_row("Normality (JB)", f"p-val: {dist['jb_pvalue']:.4f}", f"[{norm_color}]{norm_txt}[/{norm_color}]")

        risk = context_data.get("risk")
        if risk is not None and risk.get("status") == "ok":
            r52 = risk["52week"]
            r52_st = r52["state"]
            r52_color = "green" if r52_st == "near_52w_high" else "red" if r52_st == "near_52w_low" else "white"
            pos_pct_s = f"{r52['position_pct']:.1f}%" if not np.isnan(r52['position_pct']) else "N/A"
            table.add_row("52w Range", f"pos: {pos_pct_s}", f"[{r52_color}]{r52_st}[/{r52_color}]")
            
            dd_series = risk["drawdown_series"]
            curr_dd = dd_series["drawdown"].iloc[-1]
            dd_val_s = f"{curr_dd * 100.0:.2f}%"
            dd_st = "at_ath" if curr_dd == 0 else "underwater"
            dd_color = "green" if curr_dd == 0 else "red"
            table.add_row("Max Drawdown", f"curr: {dd_val_s}", f"[{dd_color}]{dd_st}[/{dd_color}]")
            
            liq = risk["liquidity"]
            liq_st = liq["state"]
            liq_color = "green" if liq_st == "high_liquidity" else "yellow" if liq_st == "moderate_liquidity" else "red"
            table.add_row("Liquidity", f"avg_v20: {liq['avg_value_20']/1e6:.1f}M", f"[{liq_color}]{liq_st}[/{liq_color}]")
            
            beta_d = risk["beta"]
            if not np.isnan(beta_d["beta"]):
                beta_st = beta_d["state"]
                beta_color = "red" if beta_st == "high_beta" else "green" if beta_st == "low_beta" else "white"
                table.add_row("Beta vs SPY", f"beta: {beta_d['beta']:.2f}", f"[{beta_color}]{beta_st}[/{beta_color}]")

    console.print(Panel(table, border_style="cyan"))

    scores_dict = context_data.get("scores") if context_data is not None else None
    if scores_dict:
        score_table = Table(title="Techna Score Profile (Independent Dimensions)", show_header=True, header_style="bold blue")
        score_table.add_column("Dimension", style="cyan")
        score_table.add_column("Score (0-100)", justify="right")
        score_table.add_column("Bar Chart", style="green")
        score_table.add_column("State Label", style="yellow")
        
        for dim, info in scores_dict.items():
            val = info["value"]
            bar_len = int(val // 5)
            bar_str = "#" * bar_len + "-" * (20 - bar_len)
            
            state = info["state_label"]
            if state in ("strong", "bullish", "high", "positive_edge"):
                state_color = "green"
            elif state in ("weak", "bearish", "low", "negative_edge"):
                state_color = "red"
            else:
                state_color = "yellow"
                
            score_table.add_row(
                dim.replace("_", " ").title(),
                f"{val}",
                f"[{state_color}]{bar_str}[/{state_color}]",
                f"[{state_color}]{state}[/{state_color}]"
            )
        console.print(Panel(score_table, border_style="blue"))

    briefing_text = context_data.get("briefing") if context_data is not None else None
    if briefing_text:
        console.print(Panel(briefing_text, title="Synthesis — Not Advice", border_style="magenta", expand=False))


# --- Phase 25: Finding Helpers for JSON Sidecar (Data-to-Text) ---------------- #

def assert_no_advice(text: str) -> None:
    """Scan finding text for advisor guardrail violation."""
    if re.search(r"\b(buy|sell|hold)\b", text, re.IGNORECASE):
        raise ValueError(f"Advisor guardrail violated: finding contains investment advice: {text}")


def trend_finding(state: str, last_cross: tuple[str, str]) -> str:
    if not state:
        res = "Insufficient history to compute this finding."
    else:
        cross_type, cross_date = last_cross
        if cross_type != "none":
            cross_str = f"Last crossover: {cross_type} on {cross_date}."
        else:
            cross_str = "No crossover detected."
        res = f"Current trend state is {state}. {cross_str}"
    assert_no_advice(res)
    return res


def momentum_finding(
    rsi_state: str,
    macd_state: str,
    last_rsi: float,
    hist: float,
    stoch_state_val: str | None = None,
    last_stoch_k: float | None = None,
) -> str:
    if not rsi_state or math.isnan(last_rsi) or math.isnan(hist):
        res = "Insufficient history to compute this finding."
    else:
        stoch_str = ""
        if stoch_state_val is not None and last_stoch_k is not None and not math.isnan(last_stoch_k):
            stoch_str = f" Stochastic slow_k is {last_stoch_k:.2f} ({stoch_state_val})."
        res = (f"RSI is {last_rsi:.2f} ({rsi_state}); MACD histogram is "
               f"{'positive' if hist >= 0 else 'negative'} ({hist:.4f}), indicating "
               f"{macd_state} momentum.{stoch_str}")
    assert_no_advice(res)
    return res


def volatility_finding(state: str, pct_b: float, upper: float, lower: float) -> str:
    if not state or math.isnan(pct_b) or math.isnan(upper) or math.isnan(lower):
        res = "Insufficient history to compute this finding."
    else:
        res = f"Bollinger Bands state is {state} with %B at {pct_b:.4f} (Upper: {upper:.2f}, Lower: {lower:.2f})."
    assert_no_advice(res)
    return res


def levels_finding(supports: list[float], resistances: list[float]) -> str:
    if not supports and not resistances:
        res = "No significant support or resistance levels detected."
    else:
        sup_str = ", ".join(f"{x:.2f}" for x in sorted(list(set(supports)))) if supports else "none"
        res_str = ", ".join(f"{x:.2f}" for x in sorted(list(set(resistances)))) if resistances else "none"
        res = f"Key support levels are [{sup_str}] and key resistance levels are [{res_str}]."
    assert_no_advice(res)
    return res


def context_finding(trend_regime: str, last_adx: float, vol_regime: str, last_atr: float, divergence_detail: str) -> str:
    if not trend_regime or math.isnan(last_adx) or math.isnan(last_atr):
        res = "Insufficient history to compute this finding."
    else:
        div_str = divergence_detail if divergence_detail else "no divergence detected"
        res = (f"Trend regime is {trend_regime} (ADX: {last_adx:.2f}), "
               f"volatility regime is {vol_regime} (ATR: {last_atr:.2f}); divergence: {div_str}.")
    assert_no_advice(res)
    return res


def relative_finding(benchmark: str, state: str, last_rs: float, last_rs_ma: float) -> str:
    if not benchmark or not state or math.isnan(last_rs) or math.isnan(last_rs_ma):
        res = "Insufficient history to compute this finding."
    else:
        res = f"Relative strength vs {benchmark} is in a {state} state (RS Ratio: {last_rs:.6f} vs SMA: {last_rs_ma:.6f})."
    assert_no_advice(res)
    return res


def seasonality_finding(best_month_name: str, best_month_ret: float, best_month_wr: float) -> str:
    if not best_month_name or best_month_name == "N/A" or math.isnan(best_month_ret):
        res = "Insufficient history to compute this finding."
    else:
        res = f"Monthly seasonality highlights: {best_month_name} historically performs best with an average return of {best_month_ret*100:.2f}% and a win rate of {best_month_wr*100:.2f}%."
    assert_no_advice(res)
    return res


def volume_finding(
    obv_state: str,
    price_slope: float,
    obv_slope: float,
    vwap_state: str,
    vwap_dist_pct: float,
    mfi_val: float | None = None,
    mfi_state_lbl: str | None = None,
    ytd_state: str | None = None,
    high_state: str | None = None,
    low_state: str | None = None,
) -> str:
    if not obv_state or math.isnan(price_slope) or math.isnan(obv_slope) or math.isnan(vwap_dist_pct):
        res = "Insufficient history to compute this finding."
    else:
        mfi_str = ""
        if mfi_val is not None and mfi_state_lbl is not None and not math.isnan(mfi_val):
            mfi_str = f" MFI(14) is {mfi_val:.2f} ({mfi_state_lbl})."
            
        avwap_str = ""
        if ytd_state is not None and high_state is not None and low_state is not None:
            avwap_str = f" Price is {ytd_state} YTD AVWAP, {high_state} 52w High AVWAP, and {low_state} 52w Low AVWAP."
            
        res = (f"OBV trend/divergence is {obv_state} (Price slope: {price_slope:.6f}, OBV slope: {obv_slope:.6f}); "
               f"VWAP (20) state is {vwap_state} (Distance: {vwap_dist_pct:.2f}%).{mfi_str}{avwap_str}")
    assert_no_advice(res)
    return res


def econometrics_finding(stationarity_state: str, lb_sig: bool, breaks_count: int, vr_state: str) -> str:
    if not stationarity_state:
        res = "Insufficient history to compute this finding."
    else:
        autocorr_str = "significant joint" if lb_sig else "no significant joint"
        breaks_str = f"{breaks_count} structural break(s) detected" if breaks_count > 0 else "no structural breaks detected"
        res = (f"Returns are {stationarity_state} with {autocorr_str} autocorrelation; "
               f"{breaks_str}, and Variance Ratio is classified as {vr_state}.")
    assert_no_advice(res)
    return res


def risk_finding(w52_state: str, max_dd_pct: float, liq_state: str, beta: float, beta_state: str) -> str:
    if not w52_state or math.isnan(max_dd_pct) or math.isnan(beta):
        res = "Insufficient history to compute this finding."
    else:
        res = (f"52-week range position is {w52_state} with a maximum drawdown of {max_dd_pct:.2f}%; "
               f"liquidity is {liq_state} and systematic risk Beta vs SPY is {beta:.2f} ({beta_state}).")
    assert_no_advice(res)
    return res


def scores_finding(ts: int, mom: int, mat: int, liq: int, vol: int, edge: int) -> str:
    res = (f"Technical score profile: Trend Strength={ts}/100, Momentum={mom}/100, "
            f"Maturity={mat}/100, Liquidity={liq}/100, Volatility={vol}/100, Statistical Edge={edge}/100.")
    assert_no_advice(res)
    return res


_PARAMETER_TABLE: list[tuple[str, list[str]]] = [
    ("Trend", ["SMA_FAST", "SMA_MID", "SMA_SLOW"]),
    ("Multiple Timeframe (weekly)", ["WEEKLY_SMA_FAST", "WEEKLY_SMA_SLOW"]),
    ("Momentum: RSI", ["RSI_PERIOD", "RSI_OVERBOUGHT", "RSI_OVERSOLD"]),
    ("Momentum: MACD", ["MACD_FAST", "MACD_SLOW", "MACD_SIGNAL"]),
    ("Momentum: Stochastic", ["STOCH_K", "STOCH_SMOOTH", "STOCH_D", "STOCH_OVERBOUGHT", "STOCH_OVERSOLD"]),
    ("Volatility: Bollinger Bands", ["BOLLINGER_WINDOW", "BOLLINGER_STD"]),
    ("Volatility: Squeeze (Keltner, same window as Bollinger)", ["BOLLINGER_WINDOW", "KC_MULT"]),
    ("Regime: ATR / ADX", ["ATR_PERIOD", "ADX_PERIOD", "ADX_TREND_THRESHOLD"]),
    ("Levels (support/resistance)", ["SWING_WINDOW", "LEVEL_CLUSTER_PCT", "LEVEL_TOP_N"]),
    ("Divergence", ["SWING_WINDOW", "DIVERGENCE_LOOKBACK"]),
    ("Volume Profile (daily)", ["VP_LOOKBACK", "VP_BINS", "VP_VALUE_AREA"]),
    ("Volume Profile (weekly)", ["VP_WEEKLY_LOOKBACK_WEEKS", "VP_BINS", "VP_VALUE_AREA"]),
    ("Fibonacci Retracement", ["FIB_LOOKBACK", "FIB_LEVELS", "FIB_TOUCH_ATR_MULT"]),
    ("Donchian Channels", ["DONCHIAN_FAST", "DONCHIAN_SLOW"]),
    ("Money Flow Index", ["MFI_PERIOD", "MFI_OVERBOUGHT", "MFI_OVERSOLD"]),
    ("Volume / VWAP", ["VWAP_DEFAULT_PERIOD", "OBV_DIVERGENCE_LOOKBACK"]),
    ("Base rates", ["BASE_RATE_HORIZONS", "BASE_RATE_MIN_SAMPLE"]),
    ("Risk context: 52-week range", ["WEEK52_WINDOW", "WEEK52_HIGH_PCT", "WEEK52_LOW_PCT"]),
    ("Risk context: liquidity / beta", ["LIQ_HIGH_VALUE", "LIQ_LOW_VALUE", "BETA_HIGH", "BETA_LOW"]),
]


def _provenance_markdown(data_provenance: Dict[str, Any] | None) -> str:
    """Return a markdown block stating exactly what input and parameters
    produced every number/chart in this report: data source, date range,
    benchmark, and every module's fixed thresholds/windows.

    Every parameter value is read live from ``techna.config`` via getattr()
    at render time -- never hand-typed -- so this can never silently drift
    from the actual constants the run used (the same discipline already
    applied to chart/indicator source-code display elsewhere in this file).
    """
    dp = data_provenance or {}
    lines = ["## Data & Parameter Provenance\n"]
    lines.append(
        "Every number and chart below was computed from exactly this input, "
        "using exactly these fixed parameters.\n"
    )
    lines.append("**Data:**\n")
    lines.append(f"- Source: `{dp.get('source', 'unknown')}`\n")
    lines.append(f"- Interval: `{dp.get('interval', 'unknown')}`\n")
    lines.append(f"- Period requested: `{dp.get('period_requested', 'unknown')}`\n")
    lines.append(
        f"- Bars used: **{dp.get('n_bars', '?')}** "
        f"(`{dp.get('first_bar_date', '?')}` to `{dp.get('last_bar_date', '?')}`)\n"
    )
    lines.append(f"- Benchmark ticker (relative strength / beta): `{dp.get('benchmark_ticker', 'unknown')}`\n")

    lines.append("\n**Parameters (fixed constants, identical for every ticker):**\n\n")
    lines.append("| Area | Parameter | Value |\n")
    lines.append("| :--- | :--- | :--- |\n")
    for area, attr_names in _PARAMETER_TABLE:
        for name in attr_names:
            value = getattr(config, name, "?")
            lines.append(f"| {area} | `{name}` | `{value}` |\n")

    lines.append(
        "\n*None of the parameters above are fitted or optimized on this "
        "ticker's history — they are fixed constants applied identically "
        "to every run, so nothing here is curve-fit to this specific stock.*\n"
    )
    return "".join(lines)


def _embed_image_markdown(png_path: Path, alt_text: str) -> str:
    """Return a markdown image cell that embeds a PNG as a base64 data URI.

    A relative-path markdown link (``![x](file.png)``) only renders as long as
    the .ipynb stays next to its sibling PNG files. Embedding the same bytes
    as a data URI makes the notebook self-contained: it renders identically
    whether opened in place, shared as a single file, or viewed on GitHub.
    No code is executed to produce this -- it is a plain markdown cell (never
    "run"), so this makes no execution claim; it only inlines pixels that
    already exist on disk from this same report run.
    """
    if not png_path.exists():
        return f"*({alt_text} chart not available for this run)*"
    b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
    return f"![{alt_text}](data:image/png;base64,{b64})"


def _chart_source_markdown(ticker: str, img_name: str) -> str:
    """Return a markdown fenced code block with the live source of the
    ``draw_*_chart`` function that produced ``img_name``.

    Fetched fresh via ``inspect.getsource()`` every time this module runs, so
    it can never silently drift from the real drawing code (no hand-copying).
    This is a plain markdown cell, not an executed code cell -- it makes no
    claim of having re-run anything, only that this is the function's current
    source.
    """
    stem = img_name[:-4] if img_name.endswith(".png") else img_name
    suffix = stem[len(ticker) + 1:] if stem.startswith(f"{ticker}_") else stem
    fn_name = f"draw_{suffix}_chart"
    fn = globals().get(fn_name)
    if fn is None:
        return f"*(source for `{fn_name}` not found)*"
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return f"*(source for `{fn_name}` unavailable)*"
    return f"**Source: `report_builder.{fn_name}`**\n```python\n{source}```"


def _indicator_source_markdown(fn: Any) -> str:
    """Return a markdown fenced code block with the live source of an
    indicator/scoring ``compute_*`` function, via ``inspect.getsource()``.

    This is the function that produced the raw numbers shown next to it
    (via ``_raw_metrics_markdown``) -- distinct from ``_chart_source_markdown``,
    which shows how a number is *drawn*, not how it is *computed*.
    """
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return f"*(source for `{fn.__name__}` unavailable)*"
    return f"**Source: `{fn.__module__}.{fn.__name__}`**\n```python\n{source}```"


def _raw_metrics_markdown(metrics: Dict[str, Any]) -> str:
    """Return a markdown block with every raw metric value (except the
    prose ``finding``), so the exact numbers behind the finding sentence and
    the chart are visible, not just their English paraphrase.
    """
    import json as _json

    raw = {k: v for k, v in metrics.items() if k != "finding"}
    if not raw:
        return "*(no additional raw metrics for this module)*"
    body = _json.dumps(raw, indent=2, default=str, ensure_ascii=False)
    return f"**Raw metric values (from the JSON sidecar):**\n```json\n{body}\n```"


def render_report_notebook(ticker: str, result_json_path: Path, out_dir: Path, context_data: Optional[Dict[str, Any]] = None) -> Path:
    """Generate a static Jupyter notebook report using nbformat."""
    import json
    import nbformat as nbf
    
    if not result_json_path.exists():
        raise FileNotFoundError(f"Result JSON sidecar not found at: {result_json_path}")
        
    with open(result_json_path, encoding="utf-8") as f:
        res = json.load(f)
        
    nb = nbf.v4.new_notebook()
    cells = []
    
    # 1. Title Block
    title = f"# Techna Analysis Report for {ticker}\n"
    title += f"- **Generated At:** `{res.get('generated_at', 'N/A')}`\n"
    title += f"- **Status:** `{res.get('status', 'ok')}`\n"
    cells.append(nbf.v4.new_markdown_cell(title))

    # 1.5. Data & Parameter Provenance -- what every number below is based on.
    cells.append(nbf.v4.new_markdown_cell(_provenance_markdown(res.get("data_provenance"))))

    # 2. Warnings
    warnings = res.get("warnings", [])
    if warnings:
        w_md = "### Warnings\n"
        for w in warnings:
            w_md += f"- ⚠️ **Warning:** {w}\n"
        cells.append(nbf.v4.new_markdown_cell(w_md))
        
    # 3. Executive Briefing
    if context_data and context_data.get("briefing"):
        briefing_text = context_data["briefing"]
        briefing_md = "## Analyst Briefing (Synthesis — Not Advice)\n"
        briefing_md += f"{briefing_text}\n"
        cells.append(nbf.v4.new_markdown_cell(briefing_md))
        
    # 4. Scores Table
    scores_dict = context_data.get("scores") if context_data else None
    if scores_dict:
        score_md = "## Score Profile (Independent Dimensions)\n"
        score_md += "| Dimension | Score (0-100) | State Label | Details / Rule Breakdown |\n"
        score_md += "| :--- | :--- | :--- | :--- |\n"
        for dim, info in scores_dict.items():
            name = dim.replace("_", " ").title()
            val = info["value"]
            state = info["state_label"]
            breakdown = "; ".join(info["rule_breakdown"])
            note = info.get("description_note", "")
            if note:
                breakdown += f" (*Note: {note}*)"
            score_md += f"| {name} | {val} | {state} | {breakdown} |\n"
        cells.append(nbf.v4.new_markdown_cell(score_md))
        
    # 5. Category Details (12 Modules)
    module_mapping: list[tuple[str, str, Any, list[Any]]] = [
        ("events", "Today's Events (State Changes)", None, []),
        ("trend", "Trend Analysis", [f"{ticker}_overview.png", f"{ticker}_candles.png"],
         [ind.compute_sma, ind.detect_cross, ind.trend_state]),
        ("mtf", "Multiple Timeframe Context (MTF)", f"{ticker}_weekly.png",
         [ind.compute_weekly_context, ind.resample_to_weekly]),
        ("momentum", "Momentum Analysis", f"{ticker}_momentum.png",
         [ind.compute_rsi, ind.compute_macd, ind.compute_stochastic]),
        ("volatility", "Volatility (Bollinger Bands)", f"{ticker}_overview.png",
         [ind.compute_bollinger, ind.bollinger_state]),
        ("squeeze", "Volatility Squeeze", None,
         [ind.compute_squeeze]),
        ("levels", "Support & Resistance Levels", f"{ticker}_levels.png",
         [ind.find_support_resistance, ind.select_levels]),
        ("volume_profile", "Volume Profile & Value Area", f"{ticker}_volume_profile.png",
         [ind.compute_volume_profile]),
        ("volume_profile_weekly", "Weekly Volume Profile & Value Area", f"{ticker}_volume_profile_weekly.png",
         [ind.compute_volume_profile_weekly]),
        ("fibonacci", "Fibonacci Retracement Levels", f"{ticker}_fibonacci.png",
         [ind.compute_fibonacci]),
        ("donchian", "Donchian Channels & Breakouts", f"{ticker}_donchian.png",
         [ind.compute_donchian]),
        ("candles", "Candlestick Patterns", f"{ticker}_candles.png",
         [ind.compute_candle_patterns]),
        ("context", "Context & Regime", f"{ticker}_regime.png",
         [ind.compute_atr, ind.compute_adx, ind.detect_divergence]),
        ("relative", "Relative Strength vs Benchmark", f"{ticker}_relative.png",
         [ind.relative_strength, ind.rebased_performance, ind.rs_state]),
        ("seasonality", "Monthly Seasonality Summary", f"{ticker}_seasonality.png",
         [ind.monthly_returns, ind.seasonality_table, ind.monthly_summary]),
        ("volume", "Volume Analysis (OBV & VWAP)", f"{ticker}_volume.png",
         [ind.compute_obv, ind.compute_vwap, ind.detect_obv_divergence, ind.vwap_state, ind.compute_mfi, ind.compute_avwap]),
        ("econometrics", "Econometric Analysis", [
            f"{ticker}_correlogram.png",
            f"{ticker}_distribution.png",
            f"{ticker}_structural_breaks.png",
            f"{ticker}_hurst.png",
            f"{ticker}_quantile_beta.png",
        ], [ind.compute_hurst_analysis, ind.compute_stationarity_tests,
            ind.compute_return_distribution_stats, ind.ljung_box_test, ind.variance_ratio_test]),
        ("risk", "Risk Context Analysis", [
            f"{ticker}_52week.png",
            f"{ticker}_drawdown.png",
            f"{ticker}_beta.png",
        ], [ind.compute_52week_range, ind.compute_drawdown_series,
            ind.compute_liquidity_metrics, ind.compute_beta]),
        ("scores", "Technical Score Profile Summary", None, [compute_dimension_scores]),
    ]

    for mod_name, title_name, img_names, compute_fns in module_mapping:
        mod = next((m for m in res.get("modules", []) if m["module"] == mod_name), None)
        if not mod:
            continue

        metrics = mod["metrics"]
        finding_text = metrics.get("finding", "No finding available.")

        mod_md = f"### {title_name}\n"
        mod_md += f"> **Status:** `{mod['status']}`\n\n"
        mod_md += f"**Finding:** {finding_text}\n"

        cells.append(nbf.v4.new_markdown_cell(mod_md))
        cells.append(nbf.v4.new_markdown_cell(_raw_metrics_markdown(metrics)))

        for fn in compute_fns:
            cells.append(nbf.v4.new_markdown_cell(_indicator_source_markdown(fn)))

        if img_names:
            names = [img_names] if isinstance(img_names, str) else img_names
            for img_name in names:
                alt = img_name.replace("_", " ").replace(".png", "").title()
                cells.append(nbf.v4.new_markdown_cell(_chart_source_markdown(ticker, img_name)))
                cells.append(nbf.v4.new_markdown_cell(_embed_image_markdown(out_dir / img_name, alt)))

    nb["cells"] = cells
    
    notebook_path = out_dir / f"{ticker}_report.ipynb"
    with open(notebook_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
        
    return notebook_path


def mtf_finding(weekly_trend: str, weekly_rsi_state: str, alignment: str) -> str:
    """Construct descriptive weekly timeframe context finding."""
    res = (f"Weekly trend context is {weekly_trend} with {weekly_rsi_state} RSI; "
           f"daily and weekly trends are {alignment}.")
    assert_no_advice(res)
    return res


def events_finding(events: list[dict]) -> str:
    """Construct descriptive summary for detected events."""
    count = len(events)
    if count == 0:
        res = "No state changes detected on the last bar."
    elif count == 1:
        res = "1 technical event detected on the last bar."
    else:
        res = f"{count} technical events detected on the last bar."
    assert_no_advice(res)
    return res


def volume_profile_finding(state: str, poc: float, vah: float, val: float) -> str:
    """Construct descriptive volume profile finding."""
    res = f"Price is {state} the volume value area (VAL: {val:.2f}, VAH: {vah:.2f}) with POC at {poc:.2f}."
    assert_no_advice(res)
    return res


def draw_volume_profile_chart(
    ticker: str,
    df: pd.DataFrame,
    vp_data: dict,
    out_path: Path,
) -> None:
    """Plot distributed volumes as horizontal bar histogram with POC & Value Area."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    volumes = np.array(vp_data["volumes"])
    bin_edges = np.array(vp_data["bins"])
    centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    heights = bin_edges[1:] - bin_edges[:-1]
    
    poc = vp_data["poc"]
    vah = vp_data["vah"]
    val = vp_data["val"]
    
    # Horizontal bars for volumes
    ax.barh(centers, volumes, height=heights, align="center", color="#3F51B5", alpha=0.5, edgecolor="black", linewidth=0.5, label="Volume Distributed")
    
    # Overlay VAH/VAL shading
    xlim_max = float(volumes.max()) * 1.1 if len(volumes) > 0 else 1.0
    ax.fill_betweenx([val, vah], 0, xlim_max, color="#00BFA5", alpha=0.15, label="Value Area (70%)")
    
    # Horizontal dashed lines
    ax.axhline(poc, color="#E91E63", linestyle="--", linewidth=1.8, label=f"POC ({poc:.2f})")
    ax.axhline(vah, color="#00BFA5", linestyle="-.", linewidth=1.5, label=f"VAH ({vah:.2f})")
    ax.axhline(val, color="#00BFA5", linestyle="-.", linewidth=1.5, label=f"VAL ({val:.2f})")
    
    # Last Close line
    last_close = float(df["Close"].iloc[-1])
    ax.axhline(last_close, color="#FFC107", linestyle=":", linewidth=2.0, label=f"Last Close ({last_close:.2f})")
    
    ax.set_xlabel("Volume Distributed")
    ax.set_ylabel("Price")
    ax.set_title(f"{ticker} — Volume Profile & Value Area")
    ax.set_xlim(0, xlim_max)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def squeeze_finding(active: bool, duration: int) -> str:
    """Construct descriptive volatility squeeze finding."""
    if active:
        res = f"Bollinger Squeeze is active (duration: {duration} bar(s)), indicating historical compression."
    else:
        res = "Volatility squeeze is not active (Bollinger Bands lie outside Keltner Channels)."
    assert_no_advice(res)
    return res


def draw_volume_profile_weekly_chart(
    ticker: str,
    df: pd.DataFrame,
    vpw_data: dict,
    out_path: Path,
) -> None:
    """Plot distributed weekly volumes as horizontal bar histogram with weekly POC & Value Area."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    volumes = np.array(vpw_data["volumes"])
    bin_edges = np.array(vpw_data["bins"])
    centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    heights = bin_edges[1:] - bin_edges[:-1]
    
    poc = vpw_data["poc_weekly"]
    vah = vpw_data["vah_weekly"]
    val = vpw_data["val_weekly"]
    
    # Horizontal bars for volumes
    ax.barh(centers, volumes, height=heights, align="center", color="#3F51B5", alpha=0.5, edgecolor="black", linewidth=0.5, label="Weekly Volume Distributed")
    
    # Overlay VAH/VAL shading
    xlim_max = float(volumes.max()) * 1.1 if len(volumes) > 0 else 1.0
    ax.fill_betweenx([val, vah], 0, xlim_max, color="#00BFA5", alpha=0.15, label="Weekly Value Area (70%)")
    
    # Horizontal dashed lines
    ax.axhline(poc, color="#E91E63", linestyle="--", linewidth=1.8, label=f"Weekly POC ({poc:.2f})")
    ax.axhline(vah, color="#00BFA5", linestyle="-.", linewidth=1.5, label=f"Weekly VAH ({vah:.2f})")
    ax.axhline(val, color="#00BFA5", linestyle="-.", linewidth=1.5, label=f"Weekly VAL ({val:.2f})")
    
    # Last Close line
    last_close = float(df["Close"].iloc[-1])
    ax.axhline(last_close, color="#FFC107", linestyle=":", linewidth=2.0, label=f"Last Close ({last_close:.2f})")
    
    ax.set_xlabel("Volume Distributed")
    ax.set_ylabel("Price")
    ax.set_title(f"{ticker} — Weekly Volume Profile & Value Area")
    ax.set_xlim(0, xlim_max)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def volume_profile_weekly_finding(state_weekly: str, poc_weekly: float, vah_weekly: float, val_weekly: float) -> str:
    """Construct descriptive weekly volume profile finding."""
    if pd.isna(vah_weekly) or pd.isna(val_weekly) or pd.isna(poc_weekly):
        res = "Insufficient history to analyze weekly volume profile."
    else:
        res = f"Weekly price is {state_weekly} the macro volume value area (VAL: {val_weekly:.2f}, VAH: {vah_weekly:.2f}) with POC at {poc_weekly:.2f}."
    assert_no_advice(res)
    return res


def draw_fibonacci_chart(
    ticker: str,
    df: pd.DataFrame,
    fib_data: dict,
    out_path: Path,
) -> None:
    """Plot daily Close price overlaid with swing high/low markers and horizontal Fibonacci levels."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    close = df["Close"]
    ax.plot(df.index, close, label="Close", color="#1f77b4", alpha=0.8)
    
    levels = fib_data["levels"]
    direction = fib_data["direction"]
    
    colors = {
        0.236: "#ff7f0e",
        0.382: "#2ca02c",
        0.5: "#d62728",
        0.618: "#9467bd",
        0.786: "#8c564b",
    }
    
    for lvl, price in levels.items():
        color = colors.get(lvl, "gray")
        ax.axhline(price, color=color, linestyle="--", linewidth=1.0, label=f"Fib {lvl:.3f} ({price:.2f})")
        ax.text(df.index[-1], price, f"  {lvl:.3f} ({price:.2f})", color=color, va="center", fontsize=8)
        
    swing_high = fib_data["swing_high"]
    swing_low = fib_data["swing_low"]
    
    ax.axhline(swing_high, color="#E91E63", linestyle=":", linewidth=1.5, label=f"Swing High ({swing_high:.2f})")
    ax.axhline(swing_low, color="#00BFA5", linestyle=":", linewidth=1.5, label=f"Swing Low ({swing_low:.2f})")
    
    # Labels sit at the RIGHT edge (df.index[-1]), matching the convention used
    # everywhere else in this file (e.g. draw_levels_chart) -- the legend is
    # anchored "upper left", so a left-edge label collides with it and becomes
    # unreadable (this happened for real: verified visually on BRK-B/AAPL).
    ax.text(df.index[-1], swing_high, f"  Swing High ({swing_high:.2f})", color="#E91E63", va="bottom", fontsize=9)
    ax.text(df.index[-1], swing_low, f"  Swing Low ({swing_low:.2f})", color="#00BFA5", va="top", fontsize=9)
    
    ax.set_ylabel("Price")
    ax.set_title(f"{ticker} — Fibonacci Retracement (Swing Direction: {direction.upper()})")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def fibonacci_finding(fib_data: dict) -> str:
    """Construct descriptive Fibonacci retracement finding."""
    status = fib_data.get("status")
    if status == "warning":
        res = "Insufficient history or flat prices to determine Fibonacci retracement levels."
    else:
        pos = fib_data["current_position"]
        lower_lvl = pos["lower_level"]
        lower_pr = pos["lower_price"]
        upper_lvl = pos["upper_level"]
        upper_pr = pos["upper_price"]
        
        stats = fib_data["respect_stats"]
        
        if lower_lvl is not None and upper_lvl is not None:
            lower_n = stats[lower_lvl]["n"]
            upper_n = stats[upper_lvl]["n"]
            lower_rel = stats[lower_lvl]["reliable"]
            upper_rel = stats[upper_lvl]["reliable"]
            
            rel_str = f"historical touch statistics are unreliable (lower n={lower_n}, upper n={upper_n})"
            if lower_rel and upper_rel:
                rel_str = f"historical touch statistics are reliable (lower n={lower_n}, upper n={upper_n})"
                
            res = (f"Price is between the {lower_lvl:.3f} ({lower_pr:.2f}) and {upper_lvl:.3f} ({upper_pr:.2f}) "
                   f"retracement levels of the 252-bar swing; {rel_str}.")
        else:
            # No level PAIR contains the price. Since the swing extremes come
            # from the same window as the price, the price cannot be outside
            # [swing_low, swing_high] -- it is in one of the two edge zones:
            # between the shallowest level and the swing high, or between the
            # deepest level and the swing low. Say which, honestly.
            sh = fib_data["swing_high"]
            sl = fib_data["swing_low"]
            level_items = sorted(fib_data["levels"].items(), key=lambda kv: kv[1])
            deepest_lvl, deepest_pr = level_items[0]
            shallowest_lvl, shallowest_pr = level_items[-1]
            close_last = fib_data.get("close_last")
            if close_last is not None and close_last > shallowest_pr:
                res = (f"Price is above the {shallowest_lvl:.3f} retracement level ({shallowest_pr:.2f}), "
                       f"in the edge zone toward the swing high ({sh:.2f}).")
            elif close_last is not None and close_last < deepest_pr:
                res = (f"Price is below the {deepest_lvl:.3f} retracement level ({deepest_pr:.2f}), "
                       f"in the edge zone toward the swing low ({sl:.2f}).")
            else:
                res = (f"Price sits at the boundary of the retracement grid within the "
                       f"252-bar swing range [{sl:.2f}, {sh:.2f}].")

    assert_no_advice(res)
    return res


def draw_donchian_chart(
    ticker: str,
    df: pd.DataFrame,
    donchian_data: dict,
    out_path: Path,
) -> None:
    """Plot daily Close price overlaid with 20-day and 55-day Donchian Channels."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    close = df["Close"]
    ax.plot(df.index, close, label="Close", color="black", linewidth=1.0)
    
    upper_20 = donchian_data["upper_20"]
    lower_20 = donchian_data["lower_20"]
    ax.fill_between(df.index, lower_20, upper_20, color="#1f77b4", alpha=0.1, label="20-day Donchian Channel")
    ax.plot(df.index, upper_20, color="#1f77b4", linestyle=":", alpha=0.5, linewidth=0.8)
    ax.plot(df.index, lower_20, color="#1f77b4", linestyle=":", alpha=0.5, linewidth=0.8)
    
    upper_55 = donchian_data["upper_55"]
    lower_55 = donchian_data["lower_55"]
    ax.plot(df.index, upper_55, color="#d62728", linestyle="--", alpha=0.7, linewidth=1.0, label="55-day Upper")
    ax.plot(df.index, lower_55, color="#2ca02c", linestyle="--", alpha=0.7, linewidth=1.0, label="55-day Lower")
    
    ax.set_ylabel("Price")
    ax.set_title(f"{ticker} — Donchian Channels (20 / 55 day)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    _save(fig, out_path)


def donchian_finding(pos_20: float, pos_55: float, breakout_desc: str | None = None) -> str:
    """Construct descriptive Donchian Channels finding."""
    if pd.isna(pos_20) or pd.isna(pos_55):
        res = "Insufficient history to analyze Donchian channels."
    else:
        br_str = ""
        if breakout_desc:
            br_str = f"; {breakout_desc}"
        res = f"Price is trading at {pos_20:.1f}% (20-day) and {pos_55:.1f}% (55-day) of their respective Donchian channels{br_str}."
    assert_no_advice(res)
    return res


def candles_finding(patterns_dict: dict) -> str:
    """Construct descriptive candlestick patterns finding."""
    active = []
    dirs = {
        "doji": "neutral",
        "hammer": "bullish",
        "shooting_star": "bearish",
        "bullish_engulfing": "bullish",
        "bearish_engulfing": "bearish",
    }
    
    for k, v in patterns_dict.items():
        if v:
            name = k.replace("_", " ").title()
            active.append(f"{name} ({dirs[k]})")
            
    if active:
        res = f"{', '.join(active)} pattern(s) detected today; no other patterns."
    else:
        res = "No candlestick patterns detected today."
        
    assert_no_advice(res)
    return res


