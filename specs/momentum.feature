Feature: Momentum indicators
  As Techna, I need to compute momentum indicators such as Relative Strength Index (RSI)
  and Moving Average Convergence Divergence (MACD)
  so that I can categorize the asset's momentum conditions (overbought, oversold, bullish, bearish).

  Scenario: RSI matches an independent Wilder-smoothing computation
    Given a series of close prices
    When I compute the Relative Strength Index (RSI) with period 14
    Then the result matches an independently computed Wilder-smoothed series
    And the first 14 rows are NaN as warm-up

  Scenario: RSI stays within the closed interval 0..100
    Given a series of close prices
    When I compute the RSI with period 14
    Then all non-NaN values are strictly between 0 and 100 inclusive

  Scenario: RSI is NaN during the warm-up period
    Given a series of close prices
    When I compute the RSI with period 14
    Then the first 13 rows of the result are NaN

  Scenario: MACD line, signal and histogram match independent EMA math
    Given a series of close prices
    When I compute the MACD with fast=12, slow=26, signal=9
    Then the macd line matches EMA(12) - EMA(26)
    And the signal line matches EMA(9) of the macd line using adjust=False
    And the histogram matches macd - signal

  Scenario: rsi_state maps thresholds to overbought/oversold/neutral
    Given an RSI value
    When the value is >= 70
    Then the RSI state is "overbought"
    When the value is <= 30
    Then the RSI state is "oversold"
    When the value is between 30 and 70
    Then the RSI state is "neutral"
