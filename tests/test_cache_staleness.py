"""Tests for the cache staleness guard in the data layer.

Without a staleness check, an automated daily run would fetch once on day one
and then silently reuse that frozen snapshot forever (the cache key is only
(ticker, interval) — no date, no TTL). These tests lock in the guard:

  * stale cache + working network  -> auto-refresh, source == "network"
  * stale cache + failing network  -> serve the stale cache WITH a warning
  * stale cache + network disabled -> serve the stale cache WITH a warning
  * fresh cache                    -> no fetch attempt at all
  * injected fetcher (test path)   -> exempt: never auto-refreshes

The guard only runs on the real network path (``fetcher is None``) so no
fixture-driven test can ever trigger a surprise refetch.
"""
from __future__ import annotations

import pandas as pd

from techna import data_layer as dl


def _frame(end: pd.Timestamp, n: int = 30) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=n, freq="D")
    return pd.DataFrame(
        {"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
        index=idx,
    )


def _seed_cache(tmp_cache, df: pd.DataFrame) -> None:
    """Write a cache file exactly the way the data layer does."""
    tmp_cache.mkdir(parents=True, exist_ok=True)
    df.to_csv(tmp_cache / "TEST_1d.csv", index=True)


STALE_END = pd.Timestamp.today().normalize() - pd.Timedelta(days=30)
FRESH_END = pd.Timestamp.today().normalize()


def test_stale_cache_is_auto_refreshed_from_network(monkeypatch, tmp_path):
    tmp_cache = tmp_path / "cache"
    _seed_cache(tmp_cache, _frame(STALE_END))

    fresh = _frame(FRESH_END)
    calls = {"n": 0}

    def fake_network_fetch(ticker, start, end, interval, period=None):
        calls["n"] += 1
        return fresh

    monkeypatch.setattr(dl, "_yfinance_fetcher", fake_network_fetch)

    res = dl.get_prices("TEST", cache_dir=tmp_cache)
    assert calls["n"] == 1
    assert res.source == "network"
    assert res.df.index.max().normalize() == FRESH_END
    assert any("refreshed from the network" in w for w in res.warnings)

    # The refreshed data must also have been written back to the cache.
    cached = pd.read_csv(tmp_cache / "TEST_1d.csv", index_col=0, parse_dates=True)
    assert cached.index.max().normalize() == FRESH_END


def test_stale_cache_survives_failed_refresh_with_warning(monkeypatch, tmp_path):
    tmp_cache = tmp_path / "cache"
    _seed_cache(tmp_cache, _frame(STALE_END))

    def broken_fetch(*a, **k):
        raise dl.NetworkError("simulated outage")

    monkeypatch.setattr(dl, "_yfinance_fetcher", broken_fetch)

    res = dl.get_prices("TEST", cache_dir=tmp_cache)
    assert res.source == "cache"                    # graceful fallback, no crash
    assert res.df.index.max().normalize() == STALE_END
    assert any("using the stale cache" in w for w in res.warnings)


def test_stale_cache_with_network_disabled_warns(tmp_path):
    tmp_cache = tmp_path / "cache"
    _seed_cache(tmp_cache, _frame(STALE_END))

    res = dl.get_prices("TEST", cache_dir=tmp_cache, allow_network=False)
    assert res.source == "cache"
    assert any("network access is disabled" in w for w in res.warnings)


def test_fresh_cache_triggers_no_fetch(monkeypatch, tmp_path):
    tmp_cache = tmp_path / "cache"
    _seed_cache(tmp_cache, _frame(FRESH_END))

    def exploding_fetch(*a, **k):
        raise AssertionError("fresh cache must not be refetched")

    monkeypatch.setattr(dl, "_yfinance_fetcher", exploding_fetch)

    res = dl.get_prices("TEST", cache_dir=tmp_cache)
    assert res.source == "cache"
    assert not any("stale" in w.lower() for w in res.warnings)


def test_injected_fetcher_is_exempt_from_staleness(tmp_path, golden_fetcher):
    """The fixture/test path must never auto-refetch, no matter how old the
    cached data is — this is what keeps every offline test deterministic."""
    tmp_cache = tmp_path / "cache"

    # First call populates the cache with (old) fixture data.
    first = dl.get_prices("TEST", cache_dir=tmp_cache, fetcher=golden_fetcher)
    assert first.source == "fixture"

    def exploding_fetcher(*a, **k):
        raise AssertionError("injected-fetcher path must never refetch")

    second = dl.get_prices("TEST", cache_dir=tmp_cache, fetcher=exploding_fetcher)
    assert second.source == "cache"
    assert not any("stale" in w.lower() for w in second.warnings)


def test_stale_refresh_respects_period_argument(monkeypatch, tmp_path):
    """The auto-refresh must forward the caller's period, not silently use
    the default."""
    tmp_cache = tmp_path / "cache"
    _seed_cache(tmp_cache, _frame(STALE_END))

    seen = {}

    def fake_network_fetch(ticker, start, end, interval, period=None):
        seen["period"] = period
        return _frame(FRESH_END)

    monkeypatch.setattr(dl, "_yfinance_fetcher", fake_network_fetch)

    dl.get_prices("TEST", cache_dir=tmp_cache, period="5y")
    assert seen["period"] == "5y"
