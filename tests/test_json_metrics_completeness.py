"""Regression tests locking in the widened JSON metrics for 5 modules.

Before this change, the ``relative``, ``seasonality``, ``volume``,
``econometrics``, and ``risk`` modules' JSON ``metrics`` dict only carried a
``state``/boolean label plus the prose ``finding`` sentence -- the actual raw
numbers that produced that finding (RS ratio, beta, best-month return, Hurst
exponent, ADF/KPSS statistics, ...) were computed locally in ``techna.py``
but never written to the sidecar. Anyone auditing the JSON (or the notebook,
which reads straight from it) had no way to check those numbers except by
reading pixel positions off a chart.

These tests lock in that every one of those raw fields is now present and
finite/sane, so this gap cannot silently reopen.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

from techna import data_layer as dl

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("techna_cli_jsonmetrics", str(ROOT / "techna.py"))
if _spec is None or _spec.loader is None:
    raise ImportError("Failed to load techna.py spec")
_cli = importlib.util.module_from_spec(_spec)
sys.modules["techna_cli_jsonmetrics"] = _cli
_spec.loader.exec_module(_cli)
main = _cli.main


def _module(result: dict, name: str) -> dict:
    return next(m for m in result["modules"] if m["module"] == name)


def _run(monkeypatch, golden_long_df, tmp_path) -> dict:
    mock_data = dl.PriceData(ticker="TEST", df=golden_long_df, source="fixture", warnings=[])
    # Self-referential benchmark: same data, so beta/RS are well-defined
    # (not skipped) rather than testing the "benchmark unavailable" path.
    monkeypatch.setattr(dl, "get_prices", lambda *a, **k: mock_data)

    exit_code = main(["TEST", "--no-interactive", "--no-chart", "--out", str(tmp_path)])
    assert exit_code == 0
    with open(tmp_path / "TEST_result.json", encoding="utf-8") as f:
        return json.load(f)


def test_relative_metrics_include_raw_rs_values(monkeypatch, golden_long_df, tmp_path):
    result = _run(monkeypatch, golden_long_df, tmp_path)
    rel = _module(result, "relative")["metrics"]
    assert rel["benchmark_ticker"] == "SPY"
    assert math.isfinite(rel["last_rs"])
    assert math.isfinite(rel["last_rs_ma"])


def test_seasonality_metrics_include_best_month_numbers(monkeypatch, golden_long_df, tmp_path):
    result = _run(monkeypatch, golden_long_df, tmp_path)
    seas = _module(result, "seasonality")["metrics"]
    assert seas["has_seasonality"] is True
    assert seas["best_month"] != "N/A"
    assert math.isfinite(seas["best_month_avg_return"])
    assert 0.0 <= seas["best_month_win_rate"] <= 1.0


def test_volume_metrics_include_slopes_and_distance(monkeypatch, golden_long_df, tmp_path):
    result = _run(monkeypatch, golden_long_df, tmp_path)
    vol = _module(result, "volume")["metrics"]
    assert math.isfinite(vol["price_slope"])
    assert math.isfinite(vol["obv_slope"])
    assert math.isfinite(vol["vwap_distance_pct"])


def test_econometrics_metrics_include_hurst_adf_kpss_jb(monkeypatch, golden_long_df, tmp_path):
    result = _run(monkeypatch, golden_long_df, tmp_path)
    econ = _module(result, "econometrics")["metrics"]
    for key in (
        "hurst_returns", "hurst_volatility", "adf_stat", "adf_pvalue",
        "kpss_stat", "kpss_pvalue", "skew", "excess_kurtosis", "jb_stat", "jb_pvalue",
    ):
        assert math.isfinite(econ[key]), f"{key} is not finite: {econ[key]}"
    assert 0.0 <= econ["hurst_returns"] <= 1.0


def test_risk_metrics_include_beta_and_drawdown(monkeypatch, golden_long_df, tmp_path):
    result = _run(monkeypatch, golden_long_df, tmp_path)
    risk = _module(result, "risk")["metrics"]
    assert math.isfinite(risk["beta"])
    assert math.isfinite(risk["position_pct_52w"])
    assert math.isfinite(risk["last_drawdown_pct"])
    assert math.isfinite(risk["avg_value_20"])
    assert risk["beta_state"] != "unknown"
    assert risk["liquidity_state"] != "unknown"
