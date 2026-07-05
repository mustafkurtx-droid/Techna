"""Regime & context indicators (ATR, ADX/DI) and regime classification.

These do NOT predict — they describe *context* so the other indicators are not
read naively (e.g. RSI=75 means something very different in a strong trend vs a
flat range). All smoothing is Wilder's RMA (the same family as RSI), which is
the single most common place these indicators are computed wrong.

Unlike the Close-only indicators, ATR and ADX need the full OHLC frame, so they
take a DataFrame with the canonical High/Low/Close columns.

Frozen math conventions (golden values depend on these):
    True Range TR[0]   = High[0] - Low[0]            (no previous close)
    True Range TR[i]   = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    Wilder RMA seed    = simple mean of the first `period` valid values,
                         placed at the period-th valid bar; then recursive
                         RMA[i] = (RMA[i-1]*(period-1) + value[i]) / period
    ATR                = RMA(TR, period)
    +DM[i]             = up   if (up > down and up > 0)   else 0   (up = H[i]-H[i-1])
    -DM[i]             = down if (down > up and down > 0) else 0   (down = L[i-1]-L[i])
    +DI / -DI          = 100 * RMA(+DM)/RMA(TR) , 100 * RMA(-DM)/RMA(TR)
    DX                 = 100 * |+DI - -DI| / (+DI + -DI)
    ADX                = RMA(DX, period)   -> warm-up is roughly 2*period bars
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from techna import config


def _wilder_rma(values: pd.Series, period: int) -> pd.Series:
    """Wilder's running moving average (RMA).

    Leading NaNs are skipped; the seed is the simple mean of the first
    ``period`` valid values placed at the period-th valid bar, after which the
    series is smoothed recursively. Assumes values are contiguous (no internal
    NaN gaps) after the first valid bar, which holds for our deterministic
    OHLC inputs.
    """
    v = values.to_numpy(dtype=float)
    n = len(v)
    out = np.full(n, np.nan)

    valid = ~np.isnan(v)
    if valid.sum() < period:
        return pd.Series(out, index=values.index)

    first = int(np.argmax(valid))            # position of the first non-NaN
    seed_end = first + period - 1
    if seed_end >= n:
        return pd.Series(out, index=values.index)

    out[seed_end] = np.mean(v[first : seed_end + 1])
    for i in range(seed_end + 1, n):
        out[i] = (out[i - 1] * (period - 1) + v[i]) / period

    return pd.Series(out, index=values.index)


def _true_range(df: pd.DataFrame) -> pd.Series:
    """Compute the True Range series. TR[0] = High[0] - Low[0]."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)  # max(axis=1) skips the NaNs at row 0 -> TR[0] = High-Low
    return tr


def compute_atr(df: pd.DataFrame, period: int = config.ATR_PERIOD) -> pd.Series:
    """Average True Range (Wilder). Warm-up of `period-1` rows is NaN."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("compute_atr requires a DataFrame with High/Low/Close")
    for col in ("High", "Low", "Close"):
        if col not in df.columns:
            raise ValueError(f"compute_atr requires a '{col}' column")
    return _wilder_rma(_true_range(df), period)


def compute_adx(df: pd.DataFrame, period: int = config.ADX_PERIOD) -> pd.DataFrame:
    """Average Directional Index with +DI / -DI (Wilder).

    Returns a DataFrame with columns ``adx``, ``plus_di``, ``minus_di``.
    ADX has a long warm-up (~2*period rows of NaN) by construction.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("compute_adx requires a DataFrame with High/Low/Close")
    for col in ("High", "Low", "Close"):
        if col not in df.columns:
            raise ValueError(f"compute_adx requires a '{col}' column")

    high, low = df["High"], df["Low"]
    up = high.diff()              # H[i] - H[i-1]
    down = -low.diff()            # L[i-1] - L[i]

    plus_dm = up.where((up > down) & (up > 0.0), 0.0)
    minus_dm = down.where((down > up) & (down > 0.0), 0.0)
    # Preserve the first-bar NaN (no directional movement is defined there).
    plus_dm[up.isna()] = np.nan
    minus_dm[down.isna()] = np.nan

    tr = _true_range(df)
    atr = _wilder_rma(tr, period)
    plus_dm_s = _wilder_rma(plus_dm, period)
    minus_dm_s = _wilder_rma(minus_dm, period)

    safe_atr = atr.replace(0.0, np.nan)
    plus_di = 100.0 * plus_dm_s / safe_atr
    minus_di = 100.0 * minus_dm_s / safe_atr

    di_sum = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    adx = _wilder_rma(dx, period)

    res = pd.DataFrame(index=df.index)
    res["adx"] = adx
    res["plus_di"] = plus_di
    res["minus_di"] = minus_di
    return res


def trend_regime(
    adx: pd.Series | float,
    plus_di: pd.Series | float,
    minus_di: pd.Series | float,
    *,
    threshold: float = config.ADX_TREND_THRESHOLD,
) -> str:
    """Classify the trend regime from the latest ADX / DI values.

    - "trending_up": ADX >= threshold and +DI >= -DI
    - "trending_down": ADX >= threshold and +DI < -DI
    - "ranging": ADX < threshold
    - "undetermined": ADX is NaN (warm-up)
    """
    a = adx.iloc[-1] if isinstance(adx, pd.Series) else adx
    p = plus_di.iloc[-1] if isinstance(plus_di, pd.Series) else plus_di
    m = minus_di.iloc[-1] if isinstance(minus_di, pd.Series) else minus_di

    if pd.isna(a):
        return "undetermined"
    if a < threshold:
        return "ranging"
    if pd.isna(p) or pd.isna(m):
        return "undetermined"
    return "trending_up" if p >= m else "trending_down"


def volatility_regime(
    atr: pd.Series,
    close: pd.Series,
    *,
    lookback: int = config.VOL_REGIME_LOOKBACK,
    high_pct: float = config.VOL_REGIME_HIGH_PCT,
    low_pct: float = config.VOL_REGIME_LOW_PCT,
) -> str:
    """Classify current volatility relative to the asset's own recent history.

    ATR is normalised by price (ATR% = ATR / Close) so it is comparable across
    time, then the latest value is percentile-ranked within the lookback
    window. This is descriptive, not predictive.

    - "high":   current ATR% at/above the `high_pct` percentile
    - "low":    current ATR% at/below the `low_pct` percentile
    - "normal": in between
    - "unknown": insufficient history
    """
    atr_pct = (atr / close.replace(0.0, np.nan)).dropna()
    window = atr_pct.iloc[-lookback:]
    if len(window) < 2:
        return "unknown"

    current = window.iloc[-1]
    rank = float((window < current).mean())  # share of history strictly below now
    if rank >= high_pct:
        return "high"
    if rank <= low_pct:
        return "low"
    return "normal"
