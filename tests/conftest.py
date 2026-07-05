"""Shared pytest fixtures. All offline — no network is ever touched."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Make the `techna` package importable without an editable install.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURE = ROOT / "tests" / "fixtures" / "golden_prices.csv"


def _load_fixture() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, index_col=0, parse_dates=True)


@pytest.fixture
def golden_path() -> Path:
    return FIXTURE


@pytest.fixture
def golden_df() -> pd.DataFrame:
    """The golden OHLCV frame as loaded from disk."""
    return _load_fixture()


@pytest.fixture
def golden_fetcher():
    """A fetcher that returns the golden fixture, ignoring its arguments.
    Used to drive the data layer entirely offline."""
    def _fetch(ticker, start, end, interval):
        return _load_fixture()

    return _fetch


FIXTURE_LONG = ROOT / "tests" / "fixtures" / "golden_long.csv"


def _load_fixture_long() -> pd.DataFrame:
    return pd.read_csv(FIXTURE_LONG, index_col=0, parse_dates=True)


@pytest.fixture
def golden_long_path() -> Path:
    return FIXTURE_LONG


@pytest.fixture
def golden_long_df() -> pd.DataFrame:
    """The long golden OHLCV frame (270 days) for longer window indicators."""
    return _load_fixture_long()


@pytest.fixture
def golden_long_fetcher():
    """A fetcher that returns the long golden fixture, ignoring its arguments."""
    def _fetch(ticker, start, end, interval):
        return _load_fixture_long()

    return _fetch


@pytest.fixture
def tmp_cache(tmp_path) -> Path:
    """An isolated, empty cache directory per test."""
    return tmp_path / "cache"
