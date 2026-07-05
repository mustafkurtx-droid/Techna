Feature: Liquidity Assessment
  Scenario: Average daily traded value calculation matches product of volume and close
    Given volume and close price series
    When I calculate liquidity metrics
    Then average daily traded value equals 20-day mean of close * volume

  Scenario: High liquidity classification
    Given a series with average 20-day traded value >= 50,000,000
    When I calculate liquidity metrics
    Then the liquidity state is high_liquidity

  Scenario: Moderate liquidity classification
    Given a series with average 20-day traded value between 5,000,000 and 50,000,000
    When I calculate liquidity metrics
    Then the liquidity state is moderate_liquidity

  Scenario: Low liquidity classification
    Given a series with average 20-day traded value < 5,000,000
    When I calculate liquidity metrics
    Then the liquidity state is low_liquidity
