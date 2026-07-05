"""Tests for the Data & Parameter Provenance section (JSON top-level +
markdown report + notebook).

Before this, the JSON sidecar's top level carried only ticker/status/
timestamp -- there was no single place recording WHAT input (date range,
source, benchmark) or WHAT fixed parameters (SMA windows, RSI period, ADX
period, ...) produced every number in every module. A reader could only
reconstruct this by reading scattered source code. These tests lock in that
the provenance block exists, is accurate, and appears in all three outputs
(JSON, markdown, notebook) from the same single source (``techna.config``),
so it can never drift or silently disappear from one of them.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from techna import config
from techna import data_layer as dl

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("techna_cli_provenance", str(ROOT / "techna.py"))
if _spec is None or _spec.loader is None:
    raise ImportError("Failed to load techna.py spec")
_cli = importlib.util.module_from_spec(_spec)
sys.modules["techna_cli_provenance"] = _cli
_spec.loader.exec_module(_cli)
main = _cli.main


def _run(monkeypatch, golden_long_df, tmp_path, **extra_args):
    mock_data = dl.PriceData(ticker="TEST", df=golden_long_df, source="fixture", warnings=[])
    monkeypatch.setattr(dl, "get_prices", lambda *a, **k: mock_data)
    args = ["TEST", "--no-interactive", "--notebook", "--out", str(tmp_path)]
    exit_code = main(args)
    assert exit_code == 0
    with open(tmp_path / "TEST_result.json", encoding="utf-8") as f:
        result = json.load(f)
    with open(tmp_path / "TEST_report.md", encoding="utf-8") as f:
        report_md = f.read()
    with open(tmp_path / "TEST_report.ipynb", encoding="utf-8") as f:
        nb = json.load(f)
    nb_text = "\n".join(
        "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
        for c in nb["cells"]
    )
    return result, report_md, nb_text


def test_json_top_level_carries_accurate_data_provenance(monkeypatch, golden_long_df, tmp_path):
    result, _, _ = _run(monkeypatch, golden_long_df, tmp_path)
    dp = result["data_provenance"]
    assert dp["source"] == "fixture"
    assert dp["interval"] == config.DEFAULT_INTERVAL
    assert dp["n_bars"] == len(golden_long_df)
    assert dp["first_bar_date"] == str(golden_long_df.index.min().date())
    assert dp["last_bar_date"] == str(golden_long_df.index.max().date())
    assert dp["benchmark_ticker"] == config.DEFAULT_BENCHMARK


def test_provenance_section_appears_in_markdown_and_notebook(monkeypatch, golden_long_df, tmp_path):
    _, report_md, nb_text = _run(monkeypatch, golden_long_df, tmp_path)
    for text in (report_md, nb_text):
        assert "Data & Parameter Provenance" in text
        assert "fixture" in text
        assert f"`{config.DEFAULT_BENCHMARK}`" in text
        # A handful of representative live-read parameters, proving the table
        # is genuinely sourced from config (not a hand-typed static block).
        assert f"`{config.RSI_PERIOD}`" in text
        assert f"`{config.DONCHIAN_FAST}`" in text
        assert f"`{config.DONCHIAN_SLOW}`" in text
        assert (
            "not fitted or optimized on this ticker" in text
            or "fixed constants applied identically" in text
        )


def test_provenance_parameters_reflect_live_config_not_stale_copies(monkeypatch, golden_long_df, tmp_path):
    """If someone changes a config constant, the provenance table must
    reflect the NEW value, proving it's read live via getattr(), not a
    hand-typed duplicate that could silently go stale."""
    monkeypatch.setattr(config, "DONCHIAN_FAST", 999)
    _, report_md, nb_text = _run(monkeypatch, golden_long_df, tmp_path)
    assert "`999`" in report_md
    assert "`999`" in nb_text


def test_beta_sample_size_is_exposed_in_risk_metrics(monkeypatch, golden_long_df, tmp_path):
    """Regression: compute_beta() already returns 'n' (aligned sample size)
    but it was never written to the JSON -- a reader could see beta's VALUE
    but not how many days of data it was computed over."""
    result, _, _ = _run(monkeypatch, golden_long_df, tmp_path)
    risk = next(m for m in result["modules"] if m["module"] == "risk")
    assert "beta_n" in risk["metrics"]
    assert isinstance(risk["metrics"]["beta_n"], int)
