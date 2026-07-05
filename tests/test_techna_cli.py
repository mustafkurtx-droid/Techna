"""Offline integration tests for the Techna CLI orchestrator (validates orchestrator.feature)."""
from __future__ import annotations


import sys
from pathlib import Path
import importlib.util

from techna import data_layer as dl

# Load techna.py dynamically to avoid collision with the techna package directory
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("techna_cli", str(ROOT / "techna.py"))
assert spec is not None, "Failed to create module spec for techna_cli"
techna_cli = importlib.util.module_from_spec(spec)
sys.modules["techna_cli"] = techna_cli
assert spec.loader is not None, "Module spec loader is missing"
spec.loader.exec_module(techna_cli)
main = techna_cli.main


def test_cli_valid_ticker_runs_successfully(monkeypatch, golden_long_df, tmp_path):
    """Scenario: Running a valid ticker produces a report and exit code 0."""
    mock_data = dl.PriceData(
        ticker="TEST",
        df=golden_long_df,
        source="fixture",
        warnings=[],
    )
    monkeypatch.setattr(dl, "get_prices", lambda *args, **kwargs: mock_data)
    
    # Run CLI
    exit_code = main(["TEST", "--no-interactive", "--out", str(tmp_path)])
    
    assert exit_code == 0
    
    # Check output files: report plus the 7 focused charts.
    report_file = tmp_path / "TEST_report.md"
    assert report_file.exists()
    for name in (
        "TEST_overview.png",
        "TEST_momentum.png",
        "TEST_regime.png",
        "TEST_candles.png",
        "TEST_levels.png",
        "TEST_baserates.png",
        "TEST_relative.png",
        "TEST_seasonality.png",
        "TEST_volume.png",
        "TEST_correlogram.png",
        "TEST_distribution.png",
        "TEST_52week.png",
        "TEST_drawdown.png",
        "TEST_beta.png",
    ):
        chart_file = tmp_path / name
        assert chart_file.exists(), f"missing chart {name}"
        assert chart_file.stat().st_size > 0
    
    content = report_file.read_text(encoding="utf-8")
    assert "uptrend" in content  # trend should be uptrend at the end of golden_long


def test_cli_invalid_ticker_fails_gracefully(monkeypatch):
    """Scenario: An invalid ticker fails gracefully with a friendly message and code 1."""
    def mock_get_prices(*args, **kwargs):
        raise dl.InvalidTickerError("TEST", "Ticker may be invalid or delisted")
        
    monkeypatch.setattr(dl, "get_prices", mock_get_prices)
    
    exit_code = main(["INVALID_TICKER", "--no-chart", "--no-interactive"])
    
    assert exit_code == 1


def test_cli_insufficient_data_is_warning_not_crash(monkeypatch, golden_df, tmp_path):
    """Scenario: Insufficient history for SMA200 is reported as a warning, not a crash."""
    # golden_df has only 40 rows, so it has insufficient history for SMA200 (needs 200)
    mock_data = dl.PriceData(
        ticker="TEST",
        df=golden_df,
        source="fixture",
        warnings=[],
    )
    monkeypatch.setattr(dl, "get_prices", lambda *args, **kwargs: mock_data)
    
    exit_code = main(["TEST", "--no-chart", "--no-interactive", "--out", str(tmp_path)])
    
    assert exit_code == 0
    
    report_file = tmp_path / "TEST_report.md"
    assert report_file.exists()
    
    content = report_file.read_text(encoding="utf-8")
    # Verify SMA200 warning / sideways state is written
    assert "sideways" in content
    assert "insufficient history" in content.lower()


def test_cli_very_short_history_does_not_crash(monkeypatch, tmp_path):
    """A ticker with 5-14 bars (RSI/Bollinger unavailable) must not crash.

    Regression: the base-rates block built `rsi >= threshold` while `rsi` was
    still None for <15 bars, raising a raw TypeError instead of degrading.
    """
    import numpy as np
    import pandas as pd

    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame(
        {
            "Open": np.linspace(100, 109, 10),
            "High": np.linspace(101, 110, 10),
            "Low": np.linspace(99, 108, 10),
            "Close": np.linspace(100, 109, 10),
            "Volume": [1000] * 10,
        },
        index=idx,
    )
    mock_data = dl.PriceData(ticker="TINY", df=df, source="fixture", warnings=[])
    monkeypatch.setattr(dl, "get_prices", lambda *args, **kwargs: mock_data)

    exit_code = main(["TINY", "--no-chart", "--no-interactive", "--out", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "TINY_report.md").exists()
