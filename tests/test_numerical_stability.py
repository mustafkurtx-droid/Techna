"""Numerical stability: extreme values must never propagate nan/inf or crash.

The headline case: a single zero/negative price (a bad provider tick) turns
log returns into -inf, which SURVIVES dropna() and used to kill the entire
econometrics block with ``ValueError: The data contains non-finite values``.
The data layer now drops such rows; these tests lock that in.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from techna import data_layer as dl
from techna.indicators.momentum import compute_rsi
from techna.indicators.regime import compute_atr
from techna.indicators.volatility import compute_bollinger

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("techna_cli_ns", str(ROOT / "techna.py"))
if _spec is None or _spec.loader is None:
    raise ImportError("Failed to load techna.py spec")
_cli = importlib.util.module_from_spec(_spec)
sys.modules["techna_cli_ns"] = _cli
_spec.loader.exec_module(_cli)
main = _cli.main


def _ohlcv_from_close(close: pd.Series, volume: float = 1000.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": close,
            "High": close.abs() + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": [volume] * len(close),
        },
        index=close.index,
    )


# --------------------------------------------------------------------------- #
# Non-positive prices: dropped at the data layer, warned, log returns finite
# --------------------------------------------------------------------------- #
def test_non_positive_prices_dropped_at_data_layer(tmp_cache):
    idx = pd.date_range("2024-01-02", periods=6, freq="D")
    close = pd.Series([100.0, 101.0, 0.0, -5.0, 102.0, 103.0], index=idx)
    raw = _ohlcv_from_close(close)

    res = dl.get_prices("test", cache_dir=tmp_cache, fetcher=lambda *a, **k: raw)

    assert len(res.df) == 4                                   # 0 and -5 rows gone
    assert (res.df["Close"] > 0).all()
    assert any("non-positive" in w.lower() for w in res.warnings)
    # The whole point: log returns are now finite end to end.
    log_ret = np.log(res.df["Close"]).diff().dropna()
    assert np.isfinite(log_ret).all()


def test_zero_price_pipeline_keeps_econometrics_alive(monkeypatch, golden_long_df, tmp_path):
    """One bad tick used to silently kill ALL econometrics via inf returns.
    With the data-layer guard the row is dropped and econometrics stays ok."""
    df = golden_long_df.copy()
    df.iloc[50, df.columns.get_loc("Close")] = 0.0            # a single bad tick

    def fetch(*a, **k):
        return df

    # Route through the real data layer (so _clean runs), offline via fetcher.
    real_get_prices = dl.get_prices
    monkeypatch.setattr(
        dl, "get_prices",
        lambda ticker, **kw: real_get_prices(
            ticker, cache_dir=tmp_path / "cache", fetcher=fetch
        ),
    )

    exit_code = main(["BADTICK", "--no-chart", "--no-interactive", "--out", str(tmp_path)])

    assert exit_code == 0
    result = json.loads((tmp_path / "BADTICK_result.json").read_text(encoding="utf-8"))
    econ = next(m for m in result["modules"] if m["module"] == "econometrics")
    assert econ["status"] == "ok"


# --------------------------------------------------------------------------- #
# Extreme spike: indicators stay finite and in range
# --------------------------------------------------------------------------- #
def test_extreme_price_spike_stays_finite():
    idx = pd.date_range("2024-01-02", periods=60, freq="D")
    vals = [100.0 + i * 0.1 for i in range(60)]
    vals[30] = 1500.0                                          # >10x spike
    close = pd.Series(vals, index=idx)
    df = _ohlcv_from_close(close)

    rsi = compute_rsi(close, 14).dropna()
    assert np.isfinite(rsi).all() and (rsi >= 0).all() and (rsi <= 100).all()

    boll = compute_bollinger(close, 20, 2.0).dropna()
    assert np.isfinite(boll[["mid", "upper", "lower"]].to_numpy()).all()

    atr = compute_atr(df, 14).dropna()
    assert np.isfinite(atr).all() and (atr >= 0).all()


# --------------------------------------------------------------------------- #
# Perfectly flat series: no division-by-zero, RSI settles at neutral 50
# --------------------------------------------------------------------------- #
def test_flat_series_is_stable():
    idx = pd.date_range("2024-01-02", periods=40, freq="D")
    close = pd.Series([100.0] * 40, index=idx)

    rsi = compute_rsi(close, 14).dropna()
    assert (rsi == 50.0).all()                                 # no gain, no loss -> neutral

    boll = compute_bollinger(close, 20, 2.0).dropna(subset=["mid"])
    assert not np.isinf(boll.to_numpy(dtype=float)).any()      # std=0 must not divide-crash
    assert (boll["upper"] == boll["lower"]).all()              # zero-width bands, finite
