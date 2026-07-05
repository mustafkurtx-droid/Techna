"""Offline tests for Levels v2 Support/Resistance Significance Filter (validates levels_v2.feature)."""
from __future__ import annotations

import pandas as pd
import pytest

from techna.indicators.levels import cluster_levels, rank_levels, select_levels


def test_cluster_levels():
    """Scenario: Nearby pivots within tolerance collapse into one level."""
    # Pivots: 100.0, 100.5, 102.0, 105.0, 105.2, 105.5
    # Tolerance: 1.0
    pivots = [100.0, 100.5, 102.0, 105.0, 105.2, 105.5]
    
    # Sort order is ascending: 100.0, 100.5, 102.0, 105.0, 105.2, 105.5
    # Differences:
    # 100.5 - 100.0 = 0.5 <= 1.0 (merged)
    # 102.0 - 100.5 = 1.5 > 1.0 (new cluster at 102.0)
    # 105.0 - 102.0 = 3.0 > 1.0 (new cluster at 105.0)
    # 105.2 - 105.0 = 0.2 <= 1.0 (merged)
    # 105.5 - 105.2 = 0.3 <= 1.0 (merged)
    
    # Expected clusters:
    # Cluster 1: [100.0, 100.5] -> mean: 100.25, touches: 2
    # Cluster 2: [102.0] -> mean: 102.0, touches: 1
    # Cluster 3: [105.0, 105.2, 105.5] -> mean: 105.23333333333333, touches: 3
    
    clusters = cluster_levels(pivots, tolerance=1.0)
    
    assert len(clusters) == 3
    
    # Cluster 1
    assert clusters[0]["price"] == pytest.approx(100.25)
    assert clusters[0]["touches"] == 2
    assert clusters[0]["members"] == [100.0, 100.5]
    
    # Cluster 2
    assert clusters[1]["price"] == pytest.approx(102.0)
    assert clusters[1]["touches"] == 1
    assert clusters[1]["members"] == [102.0]
    
    # Cluster 3
    assert clusters[2]["price"] == pytest.approx(105.23333333333333)
    assert clusters[2]["touches"] == 3
    assert clusters[2]["members"] == [105.0, 105.2, 105.5]


def test_rank_levels_and_top_n():
    """Scenario: Only the top-N strongest levels are kept, ranked deterministically."""
    clusters = [
        {"price": 100.0, "touches": 2, "members": [99.8, 100.2]},
        {"price": 102.0, "touches": 5, "members": [102.0] * 5},
        {"price": 105.0, "touches": 2, "members": [104.9, 105.1]},
        {"price": 110.0, "touches": 1, "members": [110.0]},
    ]
    
    # Expected ranking by touches descending, then price descending:
    # 1. 102.0 (touches 5)
    # 2. 105.0 (touches 2, price 105)
    # 3. 100.0 (touches 2, price 100)
    # 4. 110.0 (touches 1)
    
    # top_n = 2: keeps only 102.0 and 105.0
    ranked = rank_levels(clusters, top_n=2)
    assert len(ranked) == 2
    assert ranked[0]["price"] == 102.0
    assert ranked[1]["price"] == 105.0
    
    # top_n = 4: keeps all
    ranked_all = rank_levels(clusters, top_n=4)
    assert len(ranked_all) == 4
    assert ranked_all[0]["price"] == 102.0
    assert ranked_all[1]["price"] == 105.0
    assert ranked_all[2]["price"] == 100.0
    assert ranked_all[3]["price"] == 110.0


def test_select_levels_only_uses_confirmed_pivots():
    """Scenario: An extreme within the last k bars is never reported as a level.

    A pivot only exists where its full +/-k window is available, so a sharp dip
    on the very last bar cannot become a confirmed support level. This is the
    real look-ahead guarantee (no separate confirm flag is required).
    """
    # len 15, k=2. Confirmed dip at index 8 (value 5.0). Unconfirmed dip at the
    # last bar, index 14 (value 3.0) — find_support_resistance only scans
    # indices [k, n-k) = [2, 13), so index 14 is never evaluated.
    prices = pd.Series([10.0] * 8 + [5.0] + [10.0] * 5 + [3.0])
    assert len(prices) == 15

    res = select_levels(prices, k=2, tolerance=1.0, top_n=10)
    support_prices = [round(s["price"], 2) for s in res["supports"]]

    assert 5.0 in support_prices       # confirmed mid-series dip becomes a level
    assert 3.0 not in support_prices   # unconfirmed last-bar dip is excluded
