Feature: Trend indicators
  As Techna, I need to compute trend-following indicators like SMA, EMA,
  golden/death crosses, and the overall trend state of a price series
  so that I can categorize the asset's trend alignment.

  Scenario: SMA matches an independently computed series
    Given a series of close prices
    When I compute the Simple Moving Average (SMA) with window 3
    Then the result matches an independently computed simple average
    And the first 2 rows are NaN as warm-up

  Scenario: SMA warm-up rows are NaN
    Given a series of close prices
    When I compute the SMA with window 20
    Then the first 19 rows of the result are NaN

  Scenario: EMA matches an independent recursive computation (adjust=False)
    Given a series of close prices
    When I compute the Exponential Moving Average (EMA) with span 3 and adjust=False
    Then the result matches the recursive formula starting from the first price value

  Scenario: A golden cross is detected when the fast SMA crosses above the slow
    Given a fast price series and slow price series
    When the fast series crosses above the slow series
    Then a golden cross is detected on that specific bar
    And the cross type is recorded as "golden"

  Scenario: A death cross is detected when the fast SMA crosses below the slow
    Given a fast price series and slow price series
    When the fast series crosses below the slow series
    Then a death cross is detected on that specific bar
    And the cross type is recorded as "death"

  Scenario: No cross is reported during the warm-up (NaN) region
    Given price series containing NaN values
    When I evaluate cross detection
    Then no cross is detected for any row where either series is NaN

  Scenario: trend_state reflects price/SMA alignment
    Given a price, SMA50, and SMA200 values
    When price is above SMA200 and SMA50 is above SMA200
    Then the trend state is "uptrend"
    When price is below SMA200 and SMA50 is below SMA200
    Then the trend state is "downtrend"
    When price is between MAs or they cross without clear alignment
    Then the trend state is "sideways"
