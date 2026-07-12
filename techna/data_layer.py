"""Techna shared data layer — the single source of truth for price data.

Every indicator module consumes prices through this layer; none of them
fetch on their own. The network is hit at most once per (ticker, interval):
results are cached to disk as CSV and reused on subsequent calls.

Design notes
------------
* Network access is *injected* via a ``fetcher`` callable. The default
  fetcher uses yfinance; tests pass a fixture-backed fetcher instead, so
  the entire layer is unit-testable offline in milliseconds.
* Cache files are plain CSV so a human can open and inspect them.
* Every failure mode raises a typed ``DataLayerError`` subclass carrying a
  plain-English message — callers never see a raw traceback.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import pandas as pd

from . import config


# --------------------------------------------------------------------------- #
# Typed errors (each one always carries a friendly, user-facing message)
# --------------------------------------------------------------------------- #
class DataLayerError(Exception):
    """Base class for all data-layer failures."""


class InvalidTickerError(DataLayerError):
    """The ticker returned no data — likely invalid, misspelled, or delisted."""


class NetworkError(DataLayerError):
    """A network fetch was required but failed or was disallowed."""


class InsufficientDataError(DataLayerError):
    """Fewer usable rows than required for the requested computation."""


# A fetcher maps (ticker, start, end, interval) -> raw OHLCV DataFrame.
Fetcher = Callable[[str, Optional[str], Optional[str], str], pd.DataFrame]


@dataclass
class PriceData:
    """Result of a data-layer request: clean prices plus provenance."""

    ticker: str
    df: pd.DataFrame
    source: str                       # 'cache' | 'network' | 'fixture'
    warnings: List[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.df)


# --------------------------------------------------------------------------- #
# Default (network) fetcher
# --------------------------------------------------------------------------- #
def _yfinance_fetcher(
    ticker: str,
    start: Optional[str],
    end: Optional[str],
    interval: str,
    period: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch raw OHLCV from yfinance. Imported lazily so the data layer can
    be imported (and tested) without yfinance present."""
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise NetworkError(
            "yfinance is not installed, so live price data cannot be fetched. "
            "Install dependencies or supply cached data."
        ) from exc

    # yfinance silently defaults to ~1 month of history when neither a period
    # nor an explicit start/end is given. That is far too little for SMA200 /
    # 50-200 cross detection, so fall back to the configured default period.
    download_kwargs = dict(interval=interval, auto_adjust=True, progress=False, threads=False)
    if start is None and end is None:
        download_kwargs["period"] = period or config.DEFAULT_PERIOD
    else:
        download_kwargs["start"] = start
        download_kwargs["end"] = end

    try:
        df = yf.download(ticker, **download_kwargs)
    except Exception as exc:  # network/parse failures -> friendly message
        raise NetworkError(
            f"Could not fetch price data for '{ticker}': {exc}"
        ) from exc

    # yfinance may return MultiIndex columns for a single ticker; flatten them.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _normalize(df: Optional[pd.DataFrame], ticker: str) -> pd.DataFrame:
    """Validate and coerce a raw frame into the canonical OHLCV schema."""
    if df is None or len(df) == 0:
        raise InvalidTickerError(
            f"No price data was returned for '{ticker}'. The ticker may be "
            f"invalid, misspelled, or delisted."
        )

    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"

    missing = [c for c in config.OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise DataLayerError(
            f"Price data for '{ticker}' is missing required column(s): "
            f"{missing}. Got columns: {list(df.columns)}."
        )

    return df[config.OHLCV_COLUMNS]


def _clean(df: pd.DataFrame) -> tuple[pd.DataFrame, List[str]]:
    """Sort, dedupe, drop empty rows, and report (not silently fix) NaNs."""
    warnings: List[str] = []
    df = df.sort_index()

    # Providers occasionally return duplicate bars for the same timestamp;
    # rolling windows would double-count them. Keep the last occurrence
    # (the provider's most recent correction) and say so.
    dup = df.index.duplicated(keep="last")
    if bool(dup.any()):
        warnings.append(
            f"Dropped {int(dup.sum())} duplicate-timestamp row(s) (kept the last occurrence)."
        )
        df = df[~dup]

    all_nan = df[config.PRICE_COLUMNS].isna().all(axis=1)
    if bool(all_nan.any()):
        dropped = int(all_nan.sum())
        df = df[~all_nan]
        warnings.append(f"Dropped {dropped} row(s) that had no price data.")

    # Non-positive prices are provider garbage for equities and poison every
    # downstream log-return (log(0) = -inf survives dropna and crashes the
    # econometrics). Guard once here so no caller has to. (NaN <= 0 is False,
    # so partial-NaN rows are untouched by this filter.)
    non_positive = (df[config.PRICE_COLUMNS] <= 0).any(axis=1)
    if bool(non_positive.any()):
        warnings.append(
            f"Dropped {int(non_positive.sum())} row(s) with non-positive price "
            f"values (invalid for equity data; would corrupt log returns)."
        )
        df = df[~non_positive]

    partial_nan = int(df[config.PRICE_COLUMNS].isna().any(axis=1).sum())
    if partial_nan:
        warnings.append(
            f"{partial_nan} row(s) contain partial NaN price values; "
            f"downstream indicators should handle these explicitly."
        )

    return df, warnings


def _write_cache(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=True)


def _read_cache(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index.name = "Date"
    return df


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def get_prices(
    ticker: str,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    period: Optional[str] = None,
    interval: str = config.DEFAULT_INTERVAL,
    cache_dir: Optional[Path | str] = None,
    force_refresh: bool = False,
    allow_network: bool = True,
    fetcher: Optional[Fetcher] = None,
    min_rows: int = 1,
) -> PriceData:
    """Return clean OHLCV prices for ``ticker``, fetching at most once.

    Parameters
    ----------
    ticker : str
        Symbol to load (case-insensitive; whitespace trimmed).
    start, end : str, optional
        Date bounds passed to the fetcher (ignored once cached).
    period : str, optional
        Time period to fetch (e.g., '2y', '5y', 'max'). Part of the cache key,
        along with (start, end) when those are given instead -- a cache
        written for one period/date-range is never silently reused to
        satisfy a request for a different one.
    interval : str
        Bar interval (default daily). Part of the cache key.
    cache_dir : path, optional
        Override the shared cache directory (tests use a temp dir).
    force_refresh : bool
        Ignore any cached file and re-fetch.
    allow_network : bool
        If False and there is no cache, raise instead of fetching.
    fetcher : callable, optional
        Injected source of raw data. Defaults to the yfinance fetcher.
        When supplied, the resulting source is reported as 'fixture'.
    min_rows : int
        Minimum usable rows required, else ``InsufficientDataError``.

    Returns
    -------
    PriceData
    """
    if not ticker or not str(ticker).strip():
        raise DataLayerError("A non-empty ticker symbol is required.")

    ticker = str(ticker).strip().upper()
    cache_dir = Path(cache_dir) if cache_dir else config.CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    # The cache key MUST include how much history was requested. Without this,
    # a ticker fetched once with e.g. period="5y" would silently satisfy every
    # later request for that (ticker, interval) -- including one asking for
    # "2y" -- by returning the full 5-year file, with no error and no size
    # check. The caller's `data_provenance.period_requested` would then say
    # "2y" while the actual data spans 5 years. (Found for real: a fresh
    # request served a stale wider-period cache.)
    if start is not None or end is not None:
        span_key = f"{start or 'none'}_{end or 'none'}"
    else:
        span_key = period or config.DEFAULT_PERIOD
    span_key = re.sub(r"[^A-Za-z0-9_-]", "-", span_key)
    cache_path = cache_dir / f"{ticker}_{interval}_{span_key}.csv"

    df: Optional[pd.DataFrame] = None
    source: Optional[str] = None
    stale_warnings: List[str] = []

    # 1) Reuse cache when allowed.
    if cache_path.exists() and not force_refresh:
        df = _read_cache(cache_path)
        source = "cache"

        # Staleness guard (real network path only — injected fetchers are
        # fixtures/tests and must never trigger a surprise refetch): if the
        # cached data's last bar is older than CACHE_STALE_DAYS, refresh it;
        # if the refresh fails, keep serving the stale cache but say so.
        # Without this, a daily automated run would silently reuse its very
        # first fetch forever.
        if fetcher is None and len(df) > 0:
            last_bar = pd.Timestamp(df.index.max())
            if last_bar.tzinfo is not None:
                last_bar = last_bar.tz_localize(None)
            age_days = (pd.Timestamp.today().normalize() - last_bar.normalize()).days
            if age_days > config.CACHE_STALE_DAYS:
                if allow_network:
                    try:
                        raw = _yfinance_fetcher(ticker, start, end, interval, period=period)
                        df = _normalize(raw, ticker)
                        source = "network"
                        _write_cache(df, cache_path)
                        stale_warnings.append(
                            f"Cached data was {age_days} day(s) old (last bar "
                            f"{last_bar.date()}); refreshed from the network."
                        )
                    except DataLayerError as exc:
                        stale_warnings.append(
                            f"Cached data is {age_days} day(s) old (last bar "
                            f"{last_bar.date()}) and the refresh attempt failed "
                            f"({exc}); using the stale cache."
                        )
                else:
                    stale_warnings.append(
                        f"Cached data is {age_days} day(s) old (last bar "
                        f"{last_bar.date()}) and network access is disabled; "
                        f"results describe that older snapshot."
                    )

    # 2) Otherwise fetch (network or injected fixture).
    if df is None:
        if not allow_network:
            raise NetworkError(
                f"No cached data exists for '{ticker}' and network access is "
                f"disabled. Enable network access or provide cached data."
            )
        fetch = fetcher or _yfinance_fetcher
        import inspect
        sig = inspect.signature(fetch)
        if "period" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            raw = fetch(ticker, start, end, interval, period=period) # type: ignore
        else:
            raw = fetch(ticker, start, end, interval)
        df = _normalize(raw, ticker)
        source = "fixture" if fetcher is not None else "network"
        _write_cache(df, cache_path)

    df, warnings = _clean(df)
    warnings = stale_warnings + warnings

    if len(df) < min_rows:
        raise InsufficientDataError(
            f"Only {len(df)} usable row(s) available for '{ticker}', but at "
            f"least {min_rows} are required for this computation."
        )

    return PriceData(ticker=ticker, df=df, source=source or "cache", warnings=warnings)
