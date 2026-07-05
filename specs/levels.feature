Feature: Support and resistance
  As Techna, I need to identify historical support and resistance levels from local extrema
  so that I can locate key structural price levels.

  Scenario: A known local minimum is reported as support
    Given a series of close prices with a local minimum at index i
    When I search for support and resistance pivots with window k
    Then index i is identified as a support pivot

  Scenario: A known local maximum is reported as resistance
    Given a series of close prices with a local maximum at index i
    When I search for support and resistance pivots with window k
    Then index i is identified as a resistance pivot
