"""Divergence detection between price and a momentum oscillator (RSI/MACD).

Divergence is a genuinely "higher-level" TA concept and, importantly, it can be
made fully deterministic: detect confirmed swing points, then compare the two
most recent ones.

    Bearish divergence: price prints a HIGHER high while the oscillator prints a
                        LOWER high (waning momentum at a new price high).
    Bullish divergence: price prints a LOWER low while the oscillator prints a
                        HIGHER low (waning momentum at a new price low).

Honesty note on look-ahead: a swing point at bar i is only *confirmed* k bars
later (it must be the extreme of [i-k, i+k]). We therefore compare already-
confirmed swings — we never claim a swing on the most recent, still-forming
bars. This is the correct, non-cheating way to report divergence.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from techna import config


def find_swings(
    series: pd.Series, k: int = config.SWING_WINDOW
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """Return (swing_highs, swing_lows) as lists of (position, value).

    A bar is a swing high/low if it is the max/min of the centered window
    [i-k, i+k]. Bars within k of either end cannot be confirmed swings.
    """
    vals = series.to_numpy(dtype=float)
    n = len(vals)
    highs: List[Tuple[int, float]] = []
    lows: List[Tuple[int, float]] = []
    for i in range(k, n - k):
        window = vals[i - k : i + k + 1]
        if np.isnan(window).any():
            continue
        if vals[i] == np.max(window):
            highs.append((i, float(vals[i])))
        if vals[i] == np.min(window):
            lows.append((i, float(vals[i])))
    return highs, lows


def detect_divergence(
    price: pd.Series,
    oscillator: pd.Series,
    *,
    k: int = config.SWING_WINDOW,
    lookback: int = config.DIVERGENCE_LOOKBACK,
) -> Dict[str, object]:
    """Detect bullish/bearish divergence over the most recent `lookback` bars.

    The oscillator is sampled at the price's swing positions (classic method).
    ``price`` and ``oscillator`` must share the same index/length.

    Returns a dict::

        {"bearish": bool, "bullish": bool, "detail": str | None}
    """
    if len(price) != len(oscillator):
        raise ValueError("price and oscillator must have the same length")

    price_w = price.iloc[-lookback:]
    osc_w = oscillator.iloc[-lookback:]
    pv = price_w.to_numpy(dtype=float)
    ov = osc_w.to_numpy(dtype=float)

    highs, lows = find_swings(price_w, k)
    result: Dict[str, object] = {"bearish": False, "bullish": False, "detail": None}
    details: List[str] = []

    if len(highs) >= 2:
        (i1, _), (i2, _) = highs[-2], highs[-1]
        if not (np.isnan(ov[i1]) or np.isnan(ov[i2])):
            if pv[i2] > pv[i1] and ov[i2] < ov[i1]:
                result["bearish"] = True
                details.append(
                    "bearish: price higher high but oscillator lower high"
                )

    if len(lows) >= 2:
        (i1, _), (i2, _) = lows[-2], lows[-1]
        if not (np.isnan(ov[i1]) or np.isnan(ov[i2])):
            if pv[i2] < pv[i1] and ov[i2] > ov[i1]:
                result["bullish"] = True
                details.append(
                    "bullish: price lower low but oscillator higher low"
                )

    if details:
        result["detail"] = "; ".join(details)
    return result
