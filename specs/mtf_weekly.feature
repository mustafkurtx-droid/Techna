Feature: Multiple Timeframe Context: Weekly timeframe analysis and trend alignment
  Scenario: Partial final week is excluded from resampled weekly data
    Given daily data ending on a Tuesday
    When weekly bars are computed
    Then the final week is dropped and the last weekly bar is the prior full week

  Scenario: Alignment state reflects daily and weekly trend agreement
    Given an uptrend on both daily and weekly timeframes
    When the alignment is computed
    Then alignment is "aligned_bullish"

  Scenario: Short history produces a warning state
    Given daily price history that contains less than 40 weekly bars
    When the weekly timeframe context is computed
    Then status is "warning"
    And findings return a descriptive fallback message
