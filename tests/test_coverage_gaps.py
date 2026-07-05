"""Targeted tests for meaningful branches the suite did not exercise.

Coverage is a gap-finding tool here, not a number to chase: network paths
(yfinance fetcher, PyPI check) are deliberately untested offline, and
type-guard raises are low value. What IS covered below are real logic
branches: briefing narrative rules, the I/O-contract validation/sanitizer,
the empty-seasonality path, and the data-layer schema error.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna import data_layer as dl
from techna import io_contract
from techna.briefing import build_analyst_briefing
from techna.indicators.seasonality import monthly_summary


def _scores(trend=55, trend_label="moderate", mom=50, mom_label="neutral",
            maturity=50, maturity_label="mid"):
    return {
        "trend_strength": {"value": trend, "state_label": trend_label},
        "momentum": {"value": mom, "state_label": mom_label},
        "trend_maturity": {"value": maturity, "state_label": maturity_label},
        "liquidity": {"value": 100, "state_label": "high"},
        "volatility_level": {"value": 50, "state_label": "normal"},
        "statistical_edge": {"value": 50, "state_label": "insufficient_sample", "reliable": False},
    }


_IND = {"trend_regime": "ranging", "rsi_overbought": False, "boll_upper": False,
        "baserates_stats": []}


# --------------------------------------------------------------------------- #
# Briefing rule branches (deterministic narrative — each rule is real logic)
# --------------------------------------------------------------------------- #
def test_briefing_bullish_confirmation_branch():
    text = build_analyst_briefing(_IND, _scores(trend=80, trend_label="strong",
                                                mom=70, mom_label="bullish"))
    assert "Confirmations" in text
    assert "align bullishly" in text


def test_briefing_neutral_consolidation_branch():
    text = build_analyst_briefing(_IND, _scores(trend=30, trend_label="weak",
                                                mom=50, mom_label="neutral"))
    assert "Confirmations" in text
    assert "consolidation" in text


def test_briefing_strong_trend_bearish_momentum_contradiction():
    text = build_analyst_briefing(_IND, _scores(trend=80, trend_label="strong",
                                                mom=30, mom_label="bearish"))
    assert "Contradictions" in text
    assert "momentum is bearish" in text


def test_briefing_early_maturity_weak_momentum_contradiction():
    text = build_analyst_briefing(_IND, _scores(mom=30, mom_label="bearish",
                                                maturity=5, maturity_label="early"))
    assert "Contradictions" in text
    assert "early trend maturity" in text


# --------------------------------------------------------------------------- #
# I/O contract: validation + JSON sanitizer fallbacks
# --------------------------------------------------------------------------- #
def test_make_result_rejects_invalid_status():
    with pytest.raises(ValueError, match="status must be one of"):
        io_contract.make_result("trend", "TEST", status="great")


def test_json_safe_handles_numpy_scalars_and_objects():
    assert io_contract._json_safe(np.float64(1.5)) == 1.5     # numpy scalar -> float
    assert io_contract._json_safe(np.int32(7)) == 7

    class Odd:
        def __repr__(self):
            return "<odd>"

    assert io_contract._json_safe(Odd()) == "<odd>"           # unknown -> str fallback


# --------------------------------------------------------------------------- #
# Seasonality: empty input path
# --------------------------------------------------------------------------- #
def test_monthly_summary_empty_input_returns_nan_frame():
    empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    out = monthly_summary(empty)
    assert list(out.index) == list(range(1, 13))
    assert out["mean"].isna().all()
    assert out["win_rate"].isna().all()


# --------------------------------------------------------------------------- #
# Data layer: schema error for missing required columns
# --------------------------------------------------------------------------- #
def test_missing_required_column_raises_friendly_error(tmp_cache):
    idx = pd.date_range("2024-01-02", periods=3, freq="D")
    no_volume = pd.DataFrame(
        {"Open": [1.0] * 3, "High": [1.5] * 3, "Low": [0.5] * 3, "Close": [1.0] * 3},
        index=idx,
    )
    with pytest.raises(dl.DataLayerError, match="missing required column"):
        dl.get_prices("test", cache_dir=tmp_cache, fetcher=lambda *a, **k: no_volume)
