Feature: Multi-Dimension Scoring Layer
  Scenario: Trend strength score calculation
    Given computed indicators for strong trend strength
    When I compute the dimension scores
    Then the trend_strength score is at least 70
    And the trend_strength state_label is strong
    And the rule_breakdown lists the active scoring rules

  Scenario: Momentum score calculation
    Given computed indicators for momentum
    When I compute the dimension scores
    Then the momentum score is scaled with RSI and MACD contributions
    And the state_label matches the score category

  Scenario: Trend maturity score is descriptive
    Given computed indicators with 52-week range position
    When I compute the dimension scores
    Then the trend_maturity score matches the position percentage
    And the state_label classifications match the maturity level

  Scenario: Liquidity score maps average daily traded value
    Given average daily traded value indicators
    When I compute the dimension scores
    Then the liquidity score interpolates between low and high thresholds
    And the state_label is high, moderate, or low

  Scenario: Volatility level score is descriptive
    Given volatility indicators and Bollinger bandwidth
    When I compute the dimension scores
    Then the volatility_level score is built from regime and bandwidth
    And the state_label is high, normal, or low

  Scenario: Statistical edge score handles small sample sizes honestly
    Given empirical base rate statistics with small sample size (n < config limit)
    When I compute the dimension scores
    Then the statistical_edge score is 50
    And the state_label is insufficient_sample
    And the reliable flag is False

  Scenario: Guardrail prevents aggregate composite or buy scores
    Given any set of computed indicators
    When I compute the dimension scores
    Then there are no top-level aggregate keys in the output dictionary
    And keys like overall, total, buy, attractiveness, composite, or verdict are strictly absent
