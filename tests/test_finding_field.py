"""Offline tests for Phase 25 JSON Sidecar 'finding' field."""
from __future__ import annotations

import json
import sys
import importlib.util
from pathlib import Path

import pytest

from techna import data_layer as dl
from techna.report_builder import assert_no_advice

# Load techna.py dynamically to avoid collision with the techna package directory
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("techna_cli_finding", str(ROOT / "techna.py"))
assert spec is not None, "Failed to create module spec for techna_cli"
techna_cli = importlib.util.module_from_spec(spec)
sys.modules["techna_cli_finding"] = techna_cli
assert spec.loader is not None, "Module spec loader is missing"
spec.loader.exec_module(techna_cli)
main = techna_cli.main


def test_all_modules_have_finding_in_json(monkeypatch, golden_long_df, tmp_path):
    """Scenario: Each module's JSON metrics include a non-empty 'finding' string."""
    mock_data = dl.PriceData(
        ticker="TEST",
        df=golden_long_df,
        source="fixture",
        warnings=[],
    )
    monkeypatch.setattr(dl, "get_prices", lambda *args, **kwargs: mock_data)

    # Run CLI
    exit_code = main(["TEST", "--no-chart", "--no-interactive", "--out", str(tmp_path)])
    assert exit_code == 0

    # Load result json
    result_file = tmp_path / "TEST_result.json"
    assert result_file.exists()

    with open(result_file, encoding="utf-8") as f:
        res = json.load(f)

    # Check the 11 modules
    expected_modules = {
        "trend", "momentum", "volatility", "levels", "context",
        "relative", "seasonality", "volume", "econometrics", "risk", "scores"
    }

    modules_found = set()
    for m in res["modules"]:
        mod_name = m["module"]
        if mod_name in expected_modules:
            modules_found.add(mod_name)
            metrics = m["metrics"]
            assert "finding" in metrics, f"finding missing in module {mod_name}"
            assert isinstance(metrics["finding"], str)
            assert len(metrics["finding"].strip()) > 0
            assert "buy" not in metrics["finding"].lower()
            assert "sell" not in metrics["finding"].lower()
            assert "hold" not in metrics["finding"].lower()

    assert modules_found == expected_modules, f"Missing some expected modules: {expected_modules - modules_found}"


def test_finding_matches_report_text(monkeypatch, golden_long_df, tmp_path):
    """Scenario: The finding in the JSON matches the corresponding sentence in the markdown report."""
    mock_data = dl.PriceData(
        ticker="TEST",
        df=golden_long_df,
        source="fixture",
        warnings=[],
    )
    monkeypatch.setattr(dl, "get_prices", lambda *args, **kwargs: mock_data)

    exit_code = main(["TEST", "--no-chart", "--no-interactive", "--out", str(tmp_path)])
    assert exit_code == 0

    # Read JSON
    result_file = tmp_path / "TEST_result.json"
    with open(result_file, encoding="utf-8") as f:
        res = json.load(f)

    # Read markdown
    report_file = tmp_path / "TEST_report.md"
    report_content = report_file.read_text(encoding="utf-8")

    # Verify matching for trend and momentum
    trend_finding_json = next(m["metrics"]["finding"] for m in res["modules"] if m["module"] == "trend")
    momentum_finding_json = next(m["metrics"]["finding"] for m in res["modules"] if m["module"] == "momentum")

    # Assert they exist in markdown report
    assert trend_finding_json in report_content
    assert momentum_finding_json in report_content


def test_finding_fallback_on_insufficient_data(monkeypatch, golden_df, tmp_path):
    """Scenario: A module with insufficient data still yields a safe finding (fallback sentence)."""
    # golden_df has only 40 rows, SMA200 trend will warning out
    mock_data = dl.PriceData(
        ticker="TEST",
        df=golden_df,
        source="fixture",
        warnings=[],
    )
    monkeypatch.setattr(dl, "get_prices", lambda *args, **kwargs: mock_data)

    exit_code = main(["TEST", "--no-chart", "--no-interactive", "--out", str(tmp_path)])
    assert exit_code == 0

    result_file = tmp_path / "TEST_result.json"
    with open(result_file, encoding="utf-8") as f:
        res = json.load(f)

    trend_mod = next(m for m in res["modules"] if m["module"] == "trend")
    assert trend_mod["status"] == "warning"
    assert trend_mod["metrics"]["finding"] == "Insufficient history to compute this finding."


def test_finding_never_contains_advice_tokens():
    """Scenario: Findings never contain advice language."""
    # Test validator directly
    with pytest.raises(ValueError, match="Advisor guardrail violated"):
        assert_no_advice("We recommend you buy this asset.")

    with pytest.raises(ValueError, match="Advisor guardrail violated"):
        assert_no_advice("This is a sell signal.")

    with pytest.raises(ValueError, match="Advisor guardrail violated"):
        assert_no_advice("Investor should hold position.")

    # Safe text should not raise
    assert_no_advice("Current trend state is sideways. No crossover detected.")
