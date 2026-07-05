"""Offline tests for the I/O contract helpers (make_result + JSON sidecar)."""
from __future__ import annotations

import json

from techna import io_contract


def test_make_result_shape():
    res = io_contract.make_result("trend", "aapl", status="ok", metrics={"x": 1})
    assert set(res) == {"module", "ticker", "status", "metrics", "report_path", "warnings"}
    assert res["module"] == "trend"
    assert res["warnings"] == []


def test_overall_status_takes_the_worst():
    results = [
        io_contract.make_result("a", "T", status="ok"),
        io_contract.make_result("b", "T", status="warning"),
        io_contract.make_result("c", "T", status="ok"),
    ]
    assert io_contract.overall_status(results) == "warning"
    results.append(io_contract.make_result("d", "T", status="error"))
    assert io_contract.overall_status(results) == "error"


def test_json_safe_sanitizes_nan_and_tuples():
    safe = io_contract._json_safe({"a": float("nan"), "b": (1, 2), "c": float("inf")})
    assert safe["a"] is None          # NaN -> null
    assert safe["c"] is None          # inf -> null
    assert safe["b"] == [1, 2]        # tuple -> list


def test_write_results_json_roundtrip(tmp_path):
    results = [
        io_contract.make_result("trend", "TEST", status="ok", metrics={"state": "uptrend"}),
        io_contract.make_result(
            "momentum", "TEST", status="warning",
            metrics={"last_rsi": float("nan"), "macd": (0.5, 0.2, 0.3)},
            warnings=["short history"],
        ),
    ]
    path = io_contract.write_results_json(tmp_path, "test", "TEST_report.md", results, warnings=["w1"])

    payload = json.loads((tmp_path / "TEST_result.json").read_text(encoding="utf-8"))
    assert payload["ticker"] == "test"
    assert payload["status"] == "warning"          # worst of ok+warning
    assert payload["report_path"] == "TEST_report.md"
    assert [m["module"] for m in payload["modules"]] == ["trend", "momentum"]
    # NaN was sanitized to null (valid JSON, not the Python NaN literal).
    assert payload["modules"][1]["metrics"]["last_rsi"] is None
    assert payload["modules"][1]["metrics"]["macd"] == [0.5, 0.2, 0.3]
    assert path.endswith("TEST_result.json")
