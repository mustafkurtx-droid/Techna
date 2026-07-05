"""Offline tests for Multi-Dimension Scoring Layer (validates scoring.feature)."""
from __future__ import annotations


from techna.scoring import compute_dimension_scores


def test_trend_strength_score():
    """Verify trend strength score logic with different ADX, price location, and crossover scenarios."""
    # Scenario A: Strong trend strength (ADX=45, Price > SMA200, Golden crossover)
    # Expected points: 40 (ADX) + 30 (Price) + 30 (Golden) = 100 -> strong
    ind_strong = {
        "adx": 45.0,
        "price": 120.0,
        "sma200": 100.0,
        "last_cross": "golden",
    }
    res_strong = compute_dimension_scores(ind_strong)
    assert res_strong["trend_strength"]["value"] == 100
    assert res_strong["trend_strength"]["state_label"] == "strong"
    assert "Golden cross active (+30)" in res_strong["trend_strength"]["rule_breakdown"]
    
    # Scenario B: Weak trend strength (ADX=18, Price < SMA200, Death crossover)
    # Expected points: 10 (ADX) + 0 (Price) + 0 (Death) = 10 -> weak
    ind_weak = {
        "adx": 18.0,
        "price": 90.0,
        "sma200": 100.0,
        "last_cross": "death",
    }
    res_weak = compute_dimension_scores(ind_weak)
    assert res_weak["trend_strength"]["value"] == 10
    assert res_weak["trend_strength"]["state_label"] == "weak"


def test_momentum_score():
    """Verify momentum score matches RSI with MACD adjustments."""
    # Scenario A: Bullish momentum (RSI=50.0, MACD=bullish)
    # Expected: 50 (RSI) + 15 (MACD) = 65 -> bullish
    ind_bull = {
        "rsi": 50.0,
        "macd_state": "bullish",
    }
    res_bull = compute_dimension_scores(ind_bull)
    assert res_bull["momentum"]["value"] == 65
    assert res_bull["momentum"]["state_label"] == "bullish"
    
    # Scenario B: Bearish momentum (RSI=45.0, MACD=bearish)
    # Expected: 45 (RSI) - 15 (MACD) = 30 -> bearish
    ind_bear = {
        "rsi": 45.0,
        "macd_state": "bearish",
    }
    res_bear = compute_dimension_scores(ind_bear)
    assert res_bear["momentum"]["value"] == 30
    assert res_bear["momentum"]["state_label"] == "bearish"


def test_trend_maturity_score():
    """Verify maturity is descriptive and corresponds to 52-week position percent."""
    ind = {"position_pct": 95.0}
    res = compute_dimension_scores(ind)
    assert res["trend_maturity"]["value"] == 95
    assert res["trend_maturity"]["state_label"] == "extended"
    assert "description_note" in res["trend_maturity"]
    
    # NaN check
    ind_nan = {"position_pct": float("nan")}
    res_nan = compute_dimension_scores(ind_nan)
    assert res_nan["trend_maturity"]["value"] == 50
    assert res_nan["trend_maturity"]["state_label"] == "mid"


def test_liquidity_score():
    """Verify liquidity score maps to average daily traded value thresholds."""
    # High: >= 50M -> 100
    res_high = compute_dimension_scores({"avg_value_20": 55_000_000.0})
    assert res_high["liquidity"]["value"] == 100
    assert res_high["liquidity"]["state_label"] == "high"
    
    # Low: <= 5M -> 20
    res_low = compute_dimension_scores({"avg_value_20": 4_000_000.0})
    assert res_low["liquidity"]["value"] == 20
    assert res_low["liquidity"]["state_label"] == "low"
    
    # Moderate (Interpolated)
    # 27.5M is halfway between 5M and 50M (span 45M)
    # Expected points: 20 + 0.5 * 80 = 60
    res_mod = compute_dimension_scores({"avg_value_20": 27_500_000.0})
    assert res_mod["liquidity"]["value"] == 60
    assert res_mod["liquidity"]["state_label"] == "moderate"


def test_volatility_score():
    """Verify volatility score combines regime and bandwidth."""
    # Scenario: high regime (80) + 0.15 bandwidth (+15) = 95 -> high
    ind = {
        "volatility_regime": "high",
        "bandwidth": 0.15,
    }
    res = compute_dimension_scores(ind)
    assert res["volatility_level"]["value"] == 95
    assert res["volatility_level"]["state_label"] == "high"


def test_statistical_edge_score():
    """Verify statistical edge handles insufficient samples and matches win rates honestly."""
    # Scenario A: No condition matched
    ind_none = {"rsi_overbought": False, "boll_upper": False}
    res_none = compute_dimension_scores(ind_none)
    assert res_none["statistical_edge"]["value"] == 50
    assert res_none["statistical_edge"]["state_label"] == "insufficient_sample"
    assert res_none["statistical_edge"]["reliable"] is False
    
    # Scenario B: Condition matched, but insufficient sample size (n < 20)
    ind_low_sample = {
        "rsi_overbought": True,
        "boll_upper": False,
        "baserates_stats": [
            {"condition": "RSI >= 70", "horizon": 10, "n": 12, "win_rate": 0.65}
        ]
    }
    res_low = compute_dimension_scores(ind_low_sample)
    assert res_low["statistical_edge"]["value"] == 50
    assert res_low["statistical_edge"]["state_label"] == "insufficient_sample"
    assert res_low["statistical_edge"]["reliable"] is False
    
    # Scenario C: Condition matched, sufficient sample size (n >= 20)
    ind_edge = {
        "rsi_overbought": True,
        "boll_upper": False,
        "baserates_stats": [
            {"condition": "RSI >= 70", "horizon": 10, "n": 50, "win_rate": 0.58}
        ]
    }
    res_edge = compute_dimension_scores(ind_edge)
    assert res_edge["statistical_edge"]["value"] == 58
    assert res_edge["statistical_edge"]["state_label"] == "positive_edge"
    assert res_edge["statistical_edge"]["reliable"] is True


def test_no_aggregate_score():
    """Ensure that composite, buy or overall score keys are strictly absent."""
    ind = {
        "adx": 30.0,
        "price": 105.0,
        "sma200": 100.0,
        "last_cross": "golden",
        "rsi": 55.0,
        "macd_state": "bullish",
        "position_pct": 50.0,
        "avg_value_20": 12_000_000.0,
        "volatility_regime": "normal",
        "bandwidth": 0.10,
    }
    res = compute_dimension_scores(ind)
    
    # Assert none of the forbidden keys are present
    forbidden = {"overall", "total", "buy", "attractiveness", "composite", "verdict"}
    for key in forbidden:
        assert key not in res
