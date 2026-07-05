Feature: Today's Events: Deterministic state changes on the final trading bar
  Scenario: RSI crosses zones
    Given a series where RSI crossed above 70 on the last bar
    When event detection is run
    Then an event of type "rsi_zone_entry" with direction "bullish" is detected

  Scenario: MACD histogram flips sign
    Given a series where MACD histogram crossed below 0 on the last bar
    When event detection is run
    Then an event of type "macd_hist_flip" with direction "bearish" is detected

  Scenario: MA crossover occurs
    Given a series where SMA50 crossed above SMA200 on the last bar
    When event detection is run
    Then an event of type "ma_cross_today" with direction "bullish" is detected

  Scenario: Price crosses Bollinger Bands
    Given a series where closing price crossed below the lower Bollinger Band on the last bar
    When event detection is run
    Then an event of type "bollinger_cross" with direction "bearish" is detected

  Scenario: Price breaks 52-week range
    Given a series where high price breaks the prior 52-week high (excluding today)
    When event detection is run
    Then an event of type "range_52w_break" with direction "bullish" is detected

  Scenario: Price crosses daily VWAP
    Given a series where closing price crossed above daily VWAP on the last bar
    When event detection is run
    Then an event of type "vwap_cross" with direction "bullish" is detected

  Scenario: Structural break is recent
    Given a series where a structural break was detected 3 bars ago
    When event detection is run
    Then an event of type "structural_break_recent" with direction "neutral" is detected
