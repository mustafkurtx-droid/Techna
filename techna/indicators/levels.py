"""Levels indicators module (Support & Resistance).

Implements pivot-point based local extrema detection, clustering, ranking,
and filtering for support and resistance levels.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def find_support_resistance(prices: pd.Series, k: int = 5) -> pd.DataFrame:
    """Identify support and resistance levels from local extrema.
    
    A bar at index i is a support level if prices[i] is the minimum in [i-k, i+k].
    A bar at index i is a resistance level if prices[i] is the maximum in [i-k, i+k].
    
    Pivots are only evaluated when a full window of 2k+1 bars is available
    (i.e., k <= i < len(prices) - k) and there are no NaNs in the window.
    
    Returns:
        pd.DataFrame: Columns "support" and "resistance" containing the price
            if a pivot is found, otherwise NaN.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas.Series")
        
    res = pd.DataFrame(index=prices.index)
    res["support"] = np.nan
    res["resistance"] = np.nan
    
    n = len(prices)
    if n < 2 * k + 1:
        return res
        
    vals = prices.values
    for i in range(k, n - k):
        window = vals[i - k : i + k + 1]
        if np.isnan(window).any():
            continue
            
        current_val = vals[i]
        
        # Check support (local minimum)
        if current_val == np.min(window):
            res.loc[prices.index[i], "support"] = current_val
            
        # Check resistance (local maximum)
        if current_val == np.max(window):
            res.loc[prices.index[i], "resistance"] = current_val
            
    return res


def cluster_levels(pivot_prices: list[float], tolerance: float) -> list[dict]:
    """Cluster pivot prices that are within tolerance.
    
    Sorts prices, and starts a new cluster when the difference between consecutive
    prices exceeds the tolerance.
    
    Returns:
        list[dict]: Each dict contains:
            - "price": average price of the cluster members
            - "touches": count of members in the cluster
            - "members": list of original pivot prices in the cluster
    """
    if not pivot_prices:
        return []
        
    sorted_pivots = sorted(pivot_prices)
    clusters: list[list[float]] = []
    current_cluster: list[float] = [sorted_pivots[0]]
    
    for p in sorted_pivots[1:]:
        if p - current_cluster[-1] > tolerance:
            clusters.append(current_cluster)
            current_cluster = [p]
        else:
            current_cluster.append(p)
    clusters.append(current_cluster)
    
    result = []
    for members in clusters:
        result.append({
            "price": float(np.mean(members)),
            "touches": len(members),
            "members": members
        })
    return result


def rank_levels(clusters: list[dict], top_n: int) -> list[dict]:
    """Rank clusters by touches descending, and deterministically by price descending on ties.
    
    Returns at most top_n levels.
    """
    sorted_clusters = sorted(
        clusters,
        key=lambda c: (-c["touches"], -c["price"])
    )
    return sorted_clusters[:top_n]


def select_levels(
    prices: pd.Series,
    *,
    k: int = 5,
    tolerance: float,
    top_n: int = 5,
) -> dict[str, list[dict]]:
    """Select the top-N strongest support and resistance levels.

    Every returned level is already confirmed (no look-ahead): a pivot only
    exists where its full +/-k window is available, so ``find_support_resistance``
    never reports an extreme within the last k bars. No extra confirmation
    filter is needed.

    Returns:
        dict: {"supports": list[dict], "resistances": list[dict]}
            where each dict contains "price" and "touches".
    """
    pivots = find_support_resistance(prices, k=k)
    support_pivots = pivots["support"].dropna().tolist()
    resistance_pivots = pivots["resistance"].dropna().tolist()

    support_clusters = cluster_levels(support_pivots, tolerance)
    resistance_clusters = cluster_levels(resistance_pivots, tolerance)
    
    ranked_supports = rank_levels(support_clusters, top_n)
    ranked_resistances = rank_levels(resistance_clusters, top_n)
    
    # Strip down to price + touches
    final_supports = [
        {"price": c["price"], "touches": c["touches"]} for c in ranked_supports
    ]
    final_resistances = [
        {"price": c["price"], "touches": c["touches"]} for c in ranked_resistances
    ]
    
    return {
        "supports": final_supports,
        "resistances": final_resistances,
    }
