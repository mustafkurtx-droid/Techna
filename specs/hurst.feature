Feature: Hurst Exponent Long Memory Analysis
  Scenario: Persistent trending series has Hurst > 0.55
    Given a persistent trending series
    When I compute the Hurst exponent
    Then the resulting returns Hurst value is greater than 0.55
    And the state label is "persistent_trending"

  Scenario: Mean-reverting series has Hurst < 0.45
    Given a strongly mean-reverting series
    When I compute the Hurst exponent
    Then the resulting returns Hurst value is less than 0.45
    And the state label is "mean_reverting"

  Scenario: Volatility clustering has high volatility Hurst
    Given a series with volatility clustering
    When I run the full Hurst memory analysis
    Then the volatility Hurst exponent is greater than the returns Hurst exponent
