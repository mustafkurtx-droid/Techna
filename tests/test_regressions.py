"""Regression tests locking in previously fixed orchestrator bugs.

Each test guards one specific, real bug that existed and was fixed. If any of
these fail, a fixed bug has been re-introduced — do not weaken the assertion,
fix the code.

Bug inventory (all were live in techna.py at some point):
  1. Scoring read ``adx_df["ADX"]`` (uppercase) while compute_adx returns
     lowercase ``"adx"`` -> the check was always False and scoring silently
     used the 15.0 fallback for every ticker.
  2. Scoring received ``last_cross`` as the raw ``(type, date)`` tuple, so
     ``last_cross == "golden"`` never matched -> cross contribution was wrong.
  3. Risk context recomputed/lost ``stock_returns`` instead of reusing the
     log returns already computed by the econometrics block.
  4. A failure while computing ``range_52w`` inside the risk block could leak
     a NameError instead of degrading to a warning.
  5. ``draw_structural_breaks_chart`` with ``breaks=[]`` must still produce a
     chart (single regime band), not crash.
  6. A break index equal to ``len(df)`` (breaks are detected on the returns
     series, which is one shorter than prices) caused IndexError before the
     clamp was added — both in the chart and in regime-conditional stats.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from techna import data_layer as dl
from techna.indicators.econometrics import compute_regime_conditional_stats
from techna.report_builder import draw_structural_breaks_chart

# Load techna.py dynamically (same pattern as test_techna_cli.py) to avoid the
# name collision with the techna package.
ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("techna_cli_reg", str(ROOT / "techna.py"))
if _spec is None or _spec.loader is None:
    raise ImportError("Failed to load techna.py spec")
_cli = importlib.util.module_from_spec(_spec)
sys.modules["techna_cli_reg"] = _cli
_spec.loader.exec_module(_cli)
main = _cli.main


def _read_result_json(out_dir: Path, ticker: str) -> dict:
    return json.loads((out_dir / f"{ticker}_result.json").read_text(encoding="utf-8"))


def _module(result: dict, name: str) -> dict:
    return next(m for m in result["modules"] if m["module"] == name)


# --------------------------------------------------------------------------- #
# Bugs 1 + 2: scoring must receive the REAL ADX value and the cross TYPE string
# --------------------------------------------------------------------------- #
def test_scoring_receives_real_adx_and_cross(monkeypatch, golden_long_df, tmp_path):
    """golden_long ends in a strong clean trend: ADX ~99.5 (>=40 -> +40),
    price > SMA200 (+30), golden cross detected (+30) -> trend score exactly 100.

    Regression matrix this pins down:
      - ADX bug back ("ADX" uppercase -> 15.0 fallback): 10+30+30 = 70
      - cross-tuple bug back (tuple never equals "golden"): 40+30+15 = 85
      - both bugs back: 10+30+15 = 55
    Only the fixed wiring yields 100.
    """
    mock_data = dl.PriceData(ticker="TEST", df=golden_long_df, source="fixture", warnings=[])
    monkeypatch.setattr(dl, "get_prices", lambda *a, **k: mock_data)

    exit_code = main(["TEST", "--no-interactive", "--no-chart", "--out", str(tmp_path)])
    assert exit_code == 0

    scores = _module(_read_result_json(tmp_path, "TEST"), "scores")
    assert scores["metrics"]["trend_strength_score"] == 100


# --------------------------------------------------------------------------- #
# Bug 3: without a benchmark, risk context must reuse the existing log returns
# --------------------------------------------------------------------------- #
def test_risk_context_without_benchmark_reuses_returns(monkeypatch, golden_long_df, tmp_path):
    """When the benchmark fetch fails, the risk block must fall back to the
    already-computed log returns (not crash, not recompute wrongly): the run
    still exits 0 and the risk module reports ok."""
    mock_data = dl.PriceData(ticker="TEST", df=golden_long_df, source="fixture", warnings=[])

    def fetch(ticker, *a, **k):
        if str(ticker).upper() != "TEST":
            raise dl.DataLayerError(f"benchmark {ticker} unavailable in this test")
        return mock_data

    monkeypatch.setattr(dl, "get_prices", fetch)

    exit_code = main(["TEST", "--no-interactive", "--no-chart", "--out", str(tmp_path)])
    assert exit_code == 0

    result = _read_result_json(tmp_path, "TEST")
    assert _module(result, "risk")["status"] == "ok"          # reuse path worked
    assert _module(result, "relative")["status"] == "warning"  # benchmark skipped


# --------------------------------------------------------------------------- #
# Bug 4: a failure before range_52w is assigned must degrade, not NameError
# --------------------------------------------------------------------------- #
def test_risk_block_failure_degrades_without_nameerror(monkeypatch, golden_long_df, tmp_path):
    mock_data = dl.PriceData(ticker="TEST", df=golden_long_df, source="fixture", warnings=[])
    monkeypatch.setattr(dl, "get_prices", lambda *a, **k: mock_data)

    def boom(*a, **k):
        raise RuntimeError("simulated 52-week computation failure")

    # run() calls the name imported into the CLI module's namespace.
    monkeypatch.setattr(_cli, "compute_52week_range", boom)

    exit_code = main(["TEST", "--no-interactive", "--no-chart", "--out", str(tmp_path)])
    assert exit_code == 0                       # no NameError / no crash
    assert (tmp_path / "TEST_report.md").exists()

    result = _read_result_json(tmp_path, "TEST")
    risk = _module(result, "risk")
    assert risk["status"] == "warning"
    assert any("risk context" in w.lower() for w in risk["warnings"])


# --------------------------------------------------------------------------- #
# Bug 5: breaks=[] must still yield a chart (single regime band)
# --------------------------------------------------------------------------- #
def test_structural_breaks_chart_with_no_breaks(golden_long_df, tmp_path):
    out = tmp_path / "TEST_structural_breaks.png"
    draw_structural_breaks_chart("TEST", golden_long_df, [], out)
    assert out.exists()
    assert out.stat().st_size > 0


# --------------------------------------------------------------------------- #
# Bug 6: break index == len(df) must be clamped, never IndexError
# --------------------------------------------------------------------------- #
def _out_of_range_break(idx: int) -> dict:
    return {
        "date": "2099-01-01",
        "index": idx,
        "type": "volatility_shift",
        "var_before": 1e-4,
        "var_after": 4e-4,
        "mean_before": 0.0,
        "mean_after": 0.0,
        "lr": 50.0,
    }


def test_structural_breaks_chart_clamps_out_of_range_index(golden_long_df, tmp_path):
    out = tmp_path / "TEST_structural_breaks_oob.png"
    draw_structural_breaks_chart(
        "TEST", golden_long_df, [_out_of_range_break(len(golden_long_df))], out
    )
    assert out.exists()
    assert out.stat().st_size > 0


def test_regime_conditional_stats_clamps_out_of_range_index():
    rs = np.random.RandomState(42)
    returns = pd.Series(
        rs.normal(0.0, 0.01, 100),
        index=pd.date_range("2026-01-01", periods=100, freq="D"),
    )
    res = compute_regime_conditional_stats(returns, [_out_of_range_break(len(returns))])
    # Clamped to the last observation: a 1-obs regime, flagged too-short, no crash.
    assert res["is_split"] is True
    assert res["n_regime"] >= 1
    assert res["regime_too_short"] is True
