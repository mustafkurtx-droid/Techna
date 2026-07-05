"""Offline tests for Deterministic Analyst Briefing Synthesis (validates briefing.feature)."""
from __future__ import annotations

import pytest

from techna.briefing import build_analyst_briefing


@pytest.fixture
def base_context():
    """Returns baseline indicators and scores dicts."""
    indicators = {
        "trend_regime": "ranging",
        "volatility_regime": "high",
        "rsi_overbought": False,
        "boll_upper": False,
        "baserates_stats": []
    }
    scores = {
        "trend_strength": {"value": 55, "state_label": "moderate"},
        "momentum": {"value": 50, "state_label": "neutral"},
        "trend_maturity": {"value": 73, "state_label": "mid"},
        "liquidity": {"value": 100, "state_label": "high"},
        "volatility_level": {"value": 93, "state_label": "high"},
        "statistical_edge": {"value": 50, "state_label": "insufficient_sample", "reliable": False}
    }
    return indicators, scores


def test_briefing_deterministic_text(base_context):
    """Verify generated briefing text is formatted correctly and contains core descriptions."""
    ind, sc = base_context
    text = build_analyst_briefing(ind, sc)
    
    assert "Trend strength is characterized as moderate" in text
    assert "Current momentum is neutral" in text
    assert "Disclaimer" in text


def test_briefing_highlights_contradiction(base_context):
    """Verify clashing momentum and maturity triggers the extended maturity contradiction."""
    ind, sc = base_context
    sc["momentum"] = {"value": 75, "state_label": "bullish"}
    sc["trend_maturity"] = {"value": 95, "state_label": "extended"}
    
    text = build_analyst_briefing(ind, sc)
    assert "Contradictions" in text
    assert "strong but extended characteristics" in text


def test_briefing_asset_vs_textbook(base_context):
    """Verify textbook contradictions are generated when historical win rate contradicts standard interpretation."""
    ind, sc = base_context
    ind["rsi_overbought"] = True
    ind["baserates_stats"] = [
        {"condition": "RSI >= 70", "horizon": 10, "n": 50, "win_rate": 0.58}
    ]
    sc["statistical_edge"] = {"value": 58, "state_label": "positive_edge", "reliable": True}
    
    text = build_analyst_briefing(ind, sc)
    assert "Asset vs Textbook" in text
    assert "contradicting conventional textbook assumptions" in text
    
    # Check that it is skipped if low sample size (reliable == False)
    sc["statistical_edge"] = {"value": 50, "state_label": "insufficient_sample", "reliable": False}
    text_unreliable = build_analyst_briefing(ind, sc)
    assert "Asset vs Textbook" not in text_unreliable


def test_briefing_always_has_disclaimer(base_context):
    """Verify that the mandatory investment disclaimer is always at the end of the text."""
    ind, sc = base_context
    text = build_analyst_briefing(ind, sc)
    assert "solely the user's responsibility" in text


def test_briefing_never_advises(base_context):
    """Verify that advisor guardrail prevents any buy/sell/hold keywords in the briefing."""
    ind, sc = base_context
    
    # Build should pass fine for normal inputs
    text = build_analyst_briefing(ind, sc)
    for token in ("buy", "sell", "hold"):
        assert token not in text.lower()
        
    # Raise error if we inject a forbidden word in the indicators
    sc["trend_strength"]["state_label"] = "buy signal" # will trigger lower_text check
    with pytest.raises(ValueError, match="violates advisor guardrail"):
        build_analyst_briefing(ind, sc)
