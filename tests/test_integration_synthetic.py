"""End-to-end pipeline integration on realistic synthetic data.

Five years of seeded random-walk daily OHLCV with occasional outlier shocks —
the whole pipeline (indicators -> econometrics -> risk -> scoring -> report ->
charts -> JSON sidecar) must cooperate without an unhandled exception, and the
structured output must be complete and sane.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from techna import data_layer as dl

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("techna_cli_it", str(ROOT / "techna.py"))
if _spec is None or _spec.loader is None:
    raise ImportError("Failed to load techna.py spec")
_cli = importlib.util.module_from_spec(_spec)
sys.modules["techna_cli_it"] = _cli
_spec.loader.exec_module(_cli)
main = _cli.main

EXPECTED_MODULES = {
    "trend", "momentum", "volatility", "levels", "context", "relative",
    "seasonality", "volume", "econometrics", "risk", "scores",
}


def _synthetic_5y(seed: int = 7) -> pd.DataFrame:
    """~5 years of daily bars: geometric random walk + a few outlier shocks."""
    rs = np.random.RandomState(seed)
    n = 1260
    ret = rs.normal(0.0003, 0.015, n)
    ret[rs.choice(n, size=6, replace=False)] = rs.choice([-0.12, 0.12], size=6)  # shocks
    close = 100.0 * np.exp(np.cumsum(ret))
    idx = pd.bdate_range("2021-01-04", periods=n)
    close_s = pd.Series(close, index=idx)
    spread = close_s * 0.01
    return pd.DataFrame(
        {
            "Open": close_s.shift(1).fillna(close_s.iloc[0]),
            "High": close_s + spread,
            "Low": close_s - spread,
            "Close": close_s,
            "Volume": rs.randint(500_000, 5_000_000, n).astype(float),
        },
        index=idx,
    )


def test_full_pipeline_on_synthetic_5y_with_charts(monkeypatch, tmp_path):
    df = _synthetic_5y()
    mock = dl.PriceData(ticker="SYN", df=df, source="fixture", warnings=[])
    monkeypatch.setattr(dl, "get_prices", lambda *a, **k: mock)

    exit_code = main(["SYN", "--no-interactive", "--explain", "--out", str(tmp_path)])
    assert exit_code == 0

    # Report + at least the core charts exist and are non-empty.
    assert (tmp_path / "SYN_report.md").exists()
    for name in ("SYN_overview.png", "SYN_correlogram.png", "SYN_structural_breaks.png"):
        p = tmp_path / name
        assert p.exists() and p.stat().st_size > 0, f"missing chart {name}"

    # Structured sidecar: complete module set, nothing errored.
    result = json.loads((tmp_path / "SYN_result.json").read_text(encoding="utf-8"))
    modules = {m["module"]: m for m in result["modules"]}
    assert EXPECTED_MODULES.issubset(modules.keys())
    assert all(m["status"] in ("ok", "warning") for m in modules.values())

    # Scores are present and inside the 0-100 contract.
    trend_score = modules["scores"]["metrics"]["trend_strength_score"]
    assert 0 <= trend_score <= 100

    # 5y of data: the tail-sufficiency warning must NOT fire (n >= 750).
    assert not any("history is short" in w.lower() for w in result["warnings"])
