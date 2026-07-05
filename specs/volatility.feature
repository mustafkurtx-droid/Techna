Feature: Volatility (Bollinger Bands)
  As Techna, I need to compute Bollinger Bands (mid, upper, lower bands, %B, and bandwidth)
  so that I can categorize the asset's volatility and price location relative to the bands.

  Scenario: Bands match an independent rolling mean/std (ddof=0) computation
    Given a series of close prices
    When I compute the Bollinger Bands with window 20 and std 2.0
    Then the mid band is SMA(20)
    And the upper and lower bands match mid +/- 2 * rolling_std(ddof=0)
    And pct_b and bandwidth are computed correctly

  Scenario: Band ordering invariant holds: upper >= mid >= lower everywhere non-NaN
    Given a series of close prices
    When I compute the Bollinger Bands
    Then for all non-NaN rows, the relation upper >= mid >= lower holds true

  Scenario: Bands are NaN during the warm-up period
    Given a series of close prices
    When I compute the Bollinger Bands with window 20
    Then the first 19 rows of the result are NaN
