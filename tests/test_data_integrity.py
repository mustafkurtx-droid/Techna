"""Data-integrity edge cases: malformed / degenerate market data.

These lock in graceful degradation: the tool must warn and continue (or
cleanly refuse), never crash with KeyError / ZeroDivisionError / IndexError.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from techna import data_layer as dl
from techna.indicators.risk_context import compute_liquidity_metrics
from techna.indicators.volume import compute_obv, compute_vwap, vwap_state

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("techna_cli_di", str(ROOT / "techna.py"))
if _spec is None or _spec.loader is None:
    raise ImportError("Failed to load techna.py spec")
_cli = importlib.util.module_from_spec(_spec)
sys.modules["techna_cli_di"] = _cli
_spec.loader.exec_module(_cli)
main = _cli.main


def _ohlcv(index: pd.DatetimeIndex, close: list[float], volume=None) -> pd.DataFrame:
    c = pd.Series(close, index=index, dtype=float)
    vol = volume if volume is not None else [1000.0] * len(index)
    return pd.DataFrame(
        {"Open": c, "High": c + 0.5, "Low": c - 0.5, "Close": c, "Volume": vol},
        index=index,
    )


# --------------------------------------------------------------------------- #
# Duplicate timestamps (validates the data_layer.feature dedupe scenario)
# --------------------------------------------------------------------------- #
def test_duplicate_timestamps_deduplicated(tmp_cache):
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-03", "2024-01-04"])
    raw = _ohlcv(idx, [100.0, 101.0, 999.0, 102.0])  # 999 = the later correction

    res = dl.get_prices("test", cache_dir=tmp_cache, fetcher=lambda *a, **k: raw)

    assert res.df.index.is_unique
    assert len(res.df) == 3
    # keep="last": the provider's correction (999) wins over the first row (101).
    assert res.df.loc[pd.Timestamp("2024-01-03"), "Close"] == 999.0
    assert any("duplicate" in w.lower() for w in res.warnings)


# --------------------------------------------------------------------------- #
# Single-row market data: full pipeline must degrade, not crash
# --------------------------------------------------------------------------- #
def test_single_row_pipeline(monkeypatch, tmp_path):
    idx = pd.date_range("2024-01-02", periods=1, freq="D")
    mock = dl.PriceData(ticker="ONE", df=_ohlcv(idx, [100.0]), source="fixture", warnings=[])
    monkeypatch.setattr(dl, "get_prices", lambda *a, **k: mock)

    exit_code = main(["ONE", "--no-chart", "--no-interactive", "--out", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "ONE_report.md").exists()


# --------------------------------------------------------------------------- #
# All-NaN Volume column: volume/liquidity analyses degrade, run survives
# --------------------------------------------------------------------------- #
def test_all_nan_volume_pipeline(monkeypatch, golden_long_df, tmp_path):
    df = golden_long_df.copy()
    df["Volume"] = np.nan
    mock = dl.PriceData(ticker="NOVOL", df=df, source="fixture", warnings=[])
    monkeypatch.setattr(dl, "get_prices", lambda *a, **k: mock)

    exit_code = main(["NOVOL", "--no-chart", "--no-interactive", "--out", str(tmp_path)])

    assert exit_code == 0
    result = json.loads((tmp_path / "NOVOL_result.json").read_text(encoding="utf-8"))
    # The run degrades (no crash); price-based modules still deliver.
    assert any(m["module"] == "trend" and m["status"] == "ok" for m in result["modules"])


# --------------------------------------------------------------------------- #
# Zero-volume days: NaN (never inf), "unknown" state, low liquidity
# --------------------------------------------------------------------------- #
def test_zero_volume_days_are_graceful():
    n = 25
    zero_vol = pd.Series([0.0] * n)
    h = pd.Series([10.0] * n)
    lo = pd.Series([9.0] * n)
    c = pd.Series([9.5] * n)

    vwap = compute_vwap(h, lo, c, zero_vol, period=20)
    assert not np.isinf(vwap).any()              # 0/0 must yield NaN, never inf
    assert vwap_state(c, vwap)["state"] == "unknown"

    obv = compute_obv(c, zero_vol)               # zero volume = flat OBV, no crash
    assert (obv == 0.0).all()

    liq = compute_liquidity_metrics(zero_vol, c)
    assert liq["state"] == "low_liquidity"
    assert liq["avg_value_20"] == 0.0
