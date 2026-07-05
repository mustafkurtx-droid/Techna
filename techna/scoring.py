"""Deterministic Multi-Dimension Scoring Layer.

Translates technical indicators into 6 independent scores from 0 to 100,
accompanied by a transparent rule breakdown and state label.
Does NOT generate any aggregate, combined, or buy scores.
"""
from __future__ import annotations

import math
from typing import Any

from techna import config


def compute_dimension_scores(indicators: dict[str, Any]) -> dict[str, Any]:
    """Compute 6 independent technical dimension scores.
    
    Args:
        indicators: A dictionary of pre-computed technical indicators.
        
    Returns:
        dict: A dictionary mapping each of the 6 dimensions to its score details.
              Contains NO combined or aggregate keys.
    """
    scores = {}
    
    # 1. Trend Strength (ADX, Price vs SMA200, Crossover)
    adx_val = indicators.get("adx", 15.0)
    price_val = indicators.get("price", 100.0)
    sma200_val = indicators.get("sma200", 100.0)
    last_cross = indicators.get("last_cross", "none")
    
    ts_breakdown = []
    ts_score = 0
    
    # ADX contribution
    if adx_val >= 40.0:
        ts_score += 40
        ts_breakdown.append(f"Strong ADX trend strength: {adx_val:.1f} >= 40 (+40)")
    elif adx_val >= 25.0:
        ts_score += 25
        ts_breakdown.append(f"Moderate ADX trend strength: {adx_val:.1f} >= 25 (+25)")
    else:
        ts_score += 10
        ts_breakdown.append(f"Weak ADX trend strength: {adx_val:.1f} < 25 (+10)")
        
    # Price vs SMA200 contribution
    if price_val > sma200_val:
        ts_score += 30
        ts_breakdown.append(f"Price is above SMA200: {price_val:.2f} > {sma200_val:.2f} (+30)")
    else:
        ts_breakdown.append(f"Price is below SMA200: {price_val:.2f} <= {sma200_val:.2f} (+0)")
        
    # Crossover contribution
    if last_cross == "golden":
        ts_score += 30
        ts_breakdown.append("Golden cross active (+30)")
    elif last_cross == "death":
        ts_breakdown.append("Death cross active (+0)")
    else:
        ts_score += 15
        ts_breakdown.append("No active crossover (+15)")
        
    ts_score = max(0, min(100, ts_score))
    ts_state = "strong" if ts_score >= 70 else "moderate" if ts_score >= 40 else "weak"
    
    scores["trend_strength"] = {
        "value": ts_score,
        "rule_breakdown": ts_breakdown,
        "state_label": ts_state,
    }
    
    # 2. Momentum (RSI & MACD)
    rsi_val = indicators.get("rsi", 50.0)
    macd_st = indicators.get("macd_state", "neutral")
    
    mom_breakdown = []
    
    # Base is RSI
    mom_score = int(round(rsi_val))
    mom_breakdown.append(f"RSI base value: {rsi_val:.1f} (+{mom_score})")
    
    # MACD contribution
    if macd_st == "bullish":
        mom_score += 15
        mom_breakdown.append("MACD is bullish (+15)")
    elif macd_st == "bearish":
        mom_score -= 15
        mom_breakdown.append("MACD is bearish (-15)")
    else:
        mom_breakdown.append("MACD is neutral (+0)")
        
    mom_score = max(0, min(100, mom_score))
    mom_state = "bullish" if mom_score >= 60 else "neutral" if mom_score > 40 else "bearish"
    
    scores["momentum"] = {
        "value": mom_score,
        "rule_breakdown": mom_breakdown,
        "state_label": mom_state,
    }
    
    # 3. Trend Maturity (52-Week Range Position)
    pos_pct = indicators.get("position_pct", float("nan"))
    
    mat_breakdown = []
    if math.isnan(pos_pct):
        mat_score = 50
        mat_breakdown.append("Flat price series: position within 52w range is undefined (score 50)")
    else:
        mat_score = int(round(pos_pct))
        mat_breakdown.append(f"52-Week Range Position: {pos_pct:.1f}% (+{mat_score})")
        
    mat_score = max(0, min(100, mat_score))
    mat_state = "extended" if mat_score >= 90 else "early" if mat_score <= 10 else "mid"
    
    scores["trend_maturity"] = {
        "value": mat_score,
        "rule_breakdown": mat_breakdown,
        "state_label": mat_state,
        "description_note": "high maturity = less upside room, descriptive not bad",
    }
    
    # 4. Liquidity (20-day average daily traded value)
    liq_val = indicators.get("avg_value_20", 0.0)
    
    liq_breakdown = []
    if liq_val >= config.LIQ_HIGH_VALUE:
        liq_score = 100
        liq_breakdown.append(f"High liquidity: 20d avg value {liq_val:,.2f} >= high threshold {config.LIQ_HIGH_VALUE:,.0f} (score 100)")
    elif liq_val <= config.LIQ_LOW_VALUE:
        liq_score = 20
        liq_breakdown.append(f"Low liquidity: 20d avg value {liq_val:,.2f} <= low threshold {config.LIQ_LOW_VALUE:,.0f} (score 20)")
    else:
        # Interpolate between 20 and 100
        span = config.LIQ_HIGH_VALUE - config.LIQ_LOW_VALUE
        ratio = (liq_val - config.LIQ_LOW_VALUE) / span
        liq_score = int(round(20 + ratio * 80))
        liq_breakdown.append(
            f"Moderate liquidity: 20d avg value {liq_val:,.2f} interpolated between "
            f"{config.LIQ_LOW_VALUE:,.0f} and {config.LIQ_HIGH_VALUE:,.0f} (score {liq_score})"
        )
        
    liq_score = max(0, min(100, liq_score))
    liq_state = "high" if liq_score >= 80 else "moderate" if liq_score >= 40 else "low"
    
    scores["liquidity"] = {
        "value": liq_score,
        "rule_breakdown": liq_breakdown,
        "state_label": liq_state,
    }
    
    # 5. Volatility Level (ATR percentile regime & Bandwidth)
    vol_regime = indicators.get("volatility_regime", "normal")
    bandwidth = indicators.get("bandwidth", 0.10)
    
    vol_breakdown = []
    if vol_regime == "high":
        vol_score = 80
        vol_breakdown.append("Volatility regime is high (base 80)")
    elif vol_regime == "low":
        vol_score = 20
        vol_breakdown.append("Volatility regime is low (base 20)")
    else:
        vol_score = 50
        vol_breakdown.append("Volatility regime is normal (base 50)")
        
    bw_points = int(round(bandwidth * 100))
    vol_score += bw_points
    vol_breakdown.append(f"Bollinger Bandwidth: {bandwidth:.4f} adds (+{bw_points}) points")
    
    vol_score = max(0, min(100, vol_score))
    vol_state = "high" if vol_score >= 70 else "normal" if vol_score >= 35 else "low"
    
    scores["volatility_level"] = {
        "value": vol_score,
        "rule_breakdown": vol_breakdown,
        "state_label": vol_state,
        "description_note": "volatility level is descriptive, not inherently good or bad",
    }
    
    # 6. Statistical Edge (Empirical Base Rates matching current conditions)
    rsi_overbought = indicators.get("rsi_overbought", False)
    boll_upper = indicators.get("boll_upper", False)
    br_stats = indicators.get("baserates_stats", [])
    
    edge_breakdown = []
    edge_score = 50
    edge_state = "insufficient_sample"
    reliable = False
    
    matched_cond = None
    if boll_upper:
        matched_cond = "Close > Bollinger Upper"
    elif rsi_overbought:
        matched_cond = "RSI >= 70"
        
    if matched_cond is None:
        edge_breakdown.append("No active signal conditions (RSI >= 70 or Close > Bollinger Upper) (score 50)")
    else:
        # Look up matching condition in 10d base rate stats
        stat_match = None
        for stat in br_stats:
            if stat.get("condition") == matched_cond and stat.get("horizon") == 10:
                stat_match = stat
                break
                
        if stat_match is None:
            edge_breakdown.append(f"Active condition '{matched_cond}' has no historical base rate calculations (score 50)")
        else:
            n_val = stat_match.get("n", 0)
            win_rate = stat_match.get("win_rate", float("nan"))
            
            if n_val < config.BASE_RATE_MIN_SAMPLE or math.isnan(win_rate):
                edge_breakdown.append(
                    f"Active condition '{matched_cond}' matched but sample size (n={n_val}) "
                    f"is insufficient (< {config.BASE_RATE_MIN_SAMPLE}) (score 50)"
                )
            else:
                edge_score = int(round(win_rate * 100.0))
                reliable = True
                edge_state = "positive_edge" if edge_score >= 55 else "neutral" if edge_score >= 45 else "negative_edge"
                edge_breakdown.append(
                    f"Matched active condition '{matched_cond}' with win rate {win_rate*100.0:.1f}% "
                    f"over {n_val} samples (score {edge_score})"
                )
                
    scores["statistical_edge"] = {
        "value": edge_score,
        "rule_breakdown": edge_breakdown,
        "state_label": edge_state,
        "reliable": reliable,
    }
    
    # Assert check: No composite, verdict, buy, total, overall, or attractiveness keys
    forbidden_keys = {"overall", "total", "buy", "attractiveness", "composite", "verdict"}
    found_forbidden = forbidden_keys.intersection(scores.keys())
    if found_forbidden:
        raise ValueError(f"Forbidden aggregate keys found in scores: {found_forbidden}")
        
    return scores
