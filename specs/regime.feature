Feature: Context & regime indicators (ATR, ADX/DI)
  As Techna, I need volatility (ATR) and trend-strength (ADX) context so that
  other indicators are not read naively. These describe the regime; they do
  not predict and they give no advice.

  Scenario: ATR matches an independent Wilder computation
    Given an OHLC price frame
    When I compute the Average True Range (ATR) with period 14
    Then the result matches an independently computed Wilder-smoothed True Range
    And the first 13 rows are NaN as warm-up

  Scenario: True Range of the first bar has no previous close
    Given an OHLC price frame
    When I compute True Range
    Then the first bar's True Range equals High minus Low

  Scenario: ADX, +DI and -DI match an independent Wilder computation
    Given an OHLC price frame
    When I compute the ADX with period 14
    Then +DI, -DI and ADX match an independent directional-movement computation
    And ADX has a warm-up of roughly twice the period

  Scenario: A strong directional move yields a high ADX
    Given a price frame that trends strongly in one direction
    When I compute the ADX
    Then the latest ADX is above the trending threshold

  Scenario: Trend regime classification
    Given the latest ADX and DI values
    When ADX is at or above the threshold and +DI >= -DI
    Then the trend regime is "trending_up"
    When ADX is below the threshold
    Then the trend regime is "ranging"
    When ADX is NaN
    Then the trend regime is "undetermined"

  Scenario: Volatility regime is relative to the asset's own history
    Given an ATR series and matching close prices
    When the latest ATR% is in the top percentile of the lookback window
    Then the volatility regime is "high"
    When there is insufficient history
    Then the volatility regime is "unknown"
