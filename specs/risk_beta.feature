Feature: Systematic Risk (Beta)
  Scenario: Beta is calculated using common aligned dates
    Given stock returns and benchmark returns on overlapping dates
    When I compute beta
    Then aligned returns are used for systematic risk metrics

  Scenario: Beta equals covariance divided by benchmark variance
    Given stock returns and benchmark returns
    When I compute beta
    Then the calculated beta equals cov(stock, bench) / var(bench)

  Scenario: High beta state classification
    Given a series with beta > 1.3
    When I compute beta
    Then the systematic risk state is high_beta

  Scenario: Market beta state classification
    Given a series with beta between 0.7 and 1.3
    When I compute beta
    Then the systematic risk state is market_beta

  Scenario: Low beta state classification
    Given a series with beta < 0.7
    When I compute beta
    Then the systematic risk state is low_beta
