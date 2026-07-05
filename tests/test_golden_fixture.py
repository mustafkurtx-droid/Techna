"""The golden fixture must stay stable and hand-verifiable."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from techna import config

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "golden_prices.csv"


def test_fixture_exists():
    assert FIXTURE.exists(), "run: python tools/generate_golden.py"


def test_fixture_schema_and_shape():
    df = pd.read_csv(FIXTURE, index_col=0, parse_dates=True)
    assert list(df.columns) == config.OHLCV_COLUMNS
    assert len(df) == 40
    assert df.index.is_monotonic_increasing


def test_fixture_known_values():
    df = pd.read_csv(FIXTURE, index_col=0, parse_dates=True)
    # First and last close are hand-known anchors.
    assert df["Close"].iloc[0] == 100.00
    assert df["Close"].iloc[-1] == 123.50
    # Derivation rules hold on a sample row (index 1).
    row = df.iloc[1]
    assert row["Open"] == 100.00          # = previous close
    assert row["High"] == 102.00          # max(open, close) + 0.5
    assert row["Low"] == 99.50            # min(open, close) - 0.5


def test_no_nan_in_fixture():
    df = pd.read_csv(FIXTURE, index_col=0, parse_dates=True)
    assert not df.isna().any().any()
