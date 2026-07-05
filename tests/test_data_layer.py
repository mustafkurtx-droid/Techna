"""Offline tests for the shared data layer (validates data_layer.feature)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from techna import config
from techna import data_layer as dl


def test_fetch_returns_canonical_schema(golden_fetcher, tmp_cache):
    res = dl.get_prices("test", cache_dir=tmp_cache, fetcher=golden_fetcher)
    assert res.ticker == "TEST"                      # normalized upper-case
    assert res.source == "fixture"
    assert list(res.df.columns) == config.OHLCV_COLUMNS
    assert len(res.df) == 40
    assert res.df.index.is_monotonic_increasing


def test_fetch_once_then_reuse_cache(golden_fetcher, tmp_cache):
    first = dl.get_prices("test", cache_dir=tmp_cache, fetcher=golden_fetcher)
    assert first.source == "fixture"
    assert (tmp_cache / "TEST_1d.csv").exists()

    def exploding_fetcher(*args, **kwargs):
        raise AssertionError("fetcher must not be called once data is cached")

    second = dl.get_prices("test", cache_dir=tmp_cache, fetcher=exploding_fetcher)
    assert second.source == "cache"
    assert len(second.df) == 40


def test_force_refresh_bypasses_cache(golden_fetcher, tmp_cache):
    dl.get_prices("test", cache_dir=tmp_cache, fetcher=golden_fetcher)
    refreshed = dl.get_prices(
        "test", cache_dir=tmp_cache, fetcher=golden_fetcher, force_refresh=True
    )
    assert refreshed.source == "fixture"


def test_invalid_ticker_raises(tmp_cache):
    def empty_fetcher(*a, **k):
        return pd.DataFrame()
    with pytest.raises(dl.InvalidTickerError):
        dl.get_prices("badtick", cache_dir=tmp_cache, fetcher=empty_fetcher)


def test_network_disabled_with_empty_cache_raises(tmp_cache):
    with pytest.raises(dl.NetworkError):
        dl.get_prices("test", cache_dir=tmp_cache, allow_network=False)


def test_insufficient_data_raises(golden_fetcher, tmp_cache):
    with pytest.raises(dl.InsufficientDataError):
        dl.get_prices(
            "test", cache_dir=tmp_cache, fetcher=golden_fetcher, min_rows=200
        )


def test_all_nan_row_is_dropped_with_warning(tmp_cache, golden_df):
    df = golden_df.copy()
    df.iloc[5, [df.columns.get_loc(c) for c in config.PRICE_COLUMNS]] = np.nan

    def fetch(*a, **k):
        return df

    res = dl.get_prices("test", cache_dir=tmp_cache, fetcher=fetch)
    assert len(res.df) == 39
    assert any("Dropped" in w for w in res.warnings)


def test_empty_ticker_rejected(tmp_cache):
    with pytest.raises(dl.DataLayerError):
        dl.get_prices("   ", cache_dir=tmp_cache)
