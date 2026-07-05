"""Deterministic Analyst Briefing Synthesis Module.

Produces a flat-text rule-based briefing synthesizing indicators and scores.
Does NOT call any LLMs, network, or external APIs. Enforces strict disclaimers
and a guardrail forbidding buying/selling/holding advice.
"""
from __future__ import annotations

import re
from typing import Any


def build_analyst_briefing(indicators: dict[str, Any], scores: dict[str, Any]) -> str:
    """Synthesize technical indicators and scores into a rule-based narrative.
    
    Args:
        indicators: Pre-computed technical indicators dictionary.
        scores: Scores dictionary mapping the 6 dimensions.
        
    Returns:
        str: A narrative synthesis briefing (Synthesis — Not Advice).
    """
    trend_str = scores["trend_strength"]["state_label"]
    trend_score = scores["trend_strength"]["value"]
    adx_reg = indicators.get("trend_regime", "ranging")
    
    mom_state = scores["momentum"]["state_label"]
    mom_score = scores["momentum"]["value"]
    
    briefing_lines = [
        "## Executive Summary",
        f"Trend strength is characterized as {trend_str} (score: {trend_score}/100) and the ADX regime is {adx_reg}. "
        f"Current momentum is {mom_state} (score: {mom_score}/100).",
        ""
    ]
    
    # 1. Confirmations
    conf_list = []
    if trend_score >= 70 and mom_state == "bullish":
        conf_list.append("The indicators align bullishly: both the trend strength is strong and momentum is bullish, reflecting sustained upward coordination.")
    if trend_score < 40 and mom_state == "neutral":
        conf_list.append("The indicators align neutrally: a weak trend is accompanied by flat momentum, suggesting consolidation with no clear direction.")
    
    if conf_list:
        briefing_lines.append("## Confirmations")
        briefing_lines.extend(conf_list)
        briefing_lines.append("")
        
    # 2. Contradictions
    contra_list = []
    maturity_state = scores["trend_maturity"]["state_label"]
    
    if mom_score >= 60 and maturity_state == "extended":
        contra_list.append("The asset shows strong but extended characteristics: short-term momentum is high, but the asset is highly mature (position_pct >= 90%), sitting near the top of its 52-week range.")
    if trend_score >= 70 and mom_state == "bearish":
        contra_list.append("The trend is strong, but momentum is bearish, indicating potential divergence or cooling-off within a mature trend structure.")
    if mom_score <= 40 and maturity_state == "early":
        contra_list.append("The asset sits in its early trend maturity stage, but momentum remains bearish, pointing to ongoing downward pressure despite deep value territory.")
        
    if contra_list:
        briefing_lines.append("## Contradictions")
        briefing_lines.extend(contra_list)
        briefing_lines.append("")
        
    # 3. Asset vs Textbook
    textbook_list = []
    rsi_ob = indicators.get("rsi_overbought", False)
    boll_up = indicators.get("boll_upper", False)
    edge_reliable = scores["statistical_edge"].get("reliable", False)
    edge_state = scores["statistical_edge"]["state_label"]
    br_stats = indicators.get("baserates_stats", [])
    
    matched_cond = None
    if boll_up:
        matched_cond = "Close > Bollinger Upper"
    elif rsi_ob:
        matched_cond = "RSI >= 70"
        
    if matched_cond and edge_reliable:
        stat_match = None
        for stat in br_stats:
            if stat.get("condition") == matched_cond and stat.get("horizon") == 10:
                stat_match = stat
                break
        if stat_match:
            n_val = stat_match["n"]
            win_rate = stat_match["win_rate"]
            
            if win_rate >= 0.50:
                textbook_list.append(
                    f"Textbook theory dictates that '{matched_cond}' represents an overbought state with bearish expectations. "
                    f"However, this asset's historical empirical data shows a positive forward win rate of {win_rate*100.0:.1f}% "
                    f"over the next 10 days (sample size n={n_val}, classified as {edge_state}), contradicting conventional textbook assumptions."
                )
            else:
                textbook_list.append(
                    f"Textbook theory dictates that '{matched_cond}' represents an overbought state with bearish expectations, "
                    f"which aligns with this asset's historical empirical data showing a forward win rate of {win_rate*100.0:.1f}% "
                    f"over the next 10 days (sample size n={n_val}, classified as {edge_state})."
                )
                
    if textbook_list:
        briefing_lines.append("## Asset vs Textbook")
        briefing_lines.extend(textbook_list)
        briefing_lines.append("")
        
    # 4. Disclaimer
    briefing_lines.append("## Disclaimer")
    briefing_lines.append(
        "These are descriptive observations of historical and current technical data; "
        "all investment decisions and their consequences are solely the user's responsibility."
    )
    
    full_text = "\n".join(briefing_lines)
    
    # Advisor Guardrail: no 'buy', 'sell', or 'hold' as WHOLE words. Word
    # boundaries avoid false positives on "threshold"/"household"/"stronghold".
    lower_text = full_text.lower()
    forbidden = ["buy", "sell", "hold"]
    for tok in forbidden:
        if re.search(rf"\b{tok}\b", lower_text):
            raise ValueError(f"Briefing generation violates advisor guardrail: forbidden token '{tok}' found.")
            
    return full_text
