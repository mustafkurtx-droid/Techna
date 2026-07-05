Feature: Quantile Regression Beta Analysis
  Scenario: Symmetric returns have symmetric quantile beta
    Given stock and benchmark returns with symmetric correlation
    When I run the quantile beta analysis
    Then the low-quantile beta and high-quantile beta are close to each other
    And the asymmetry state label is "symmetric_beta"

  Scenario: Downside sensitive returns have higher low-quantile beta
    Given stock returns that are more sensitive to benchmark declines
    When I run the quantile beta analysis
    Then the 5% quantile beta is higher than the 95% quantile beta by more than the threshold
    And the asymmetry state label is "downside_sensitive"

  Scenario: Upside sensitive returns have higher high-quantile beta
    Given stock returns that are more sensitive to benchmark rises
    When I run the quantile beta analysis
    Then the 5% quantile beta is lower than the 95% quantile beta by more than the threshold
    And the asymmetry state label is "upside_sensitive"

  Scenario: The asymmetry claim is qualified by its own confidence intervals
    Given an asymmetry classification based on point estimates
    When the tail confidence intervals overlap
    Then the result carries asymmetry_significant = False
    And the report states the finding is not statistically significant
    When the tail confidence intervals are disjoint
    Then the result carries asymmetry_significant = True
