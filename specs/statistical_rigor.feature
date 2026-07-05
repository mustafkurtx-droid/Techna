Feature: Statistical Rigor Package
  Scenario: Ljung-Box test for autocorrelation
    Given a series of IID returns
    When I run the Ljung-Box test
    Then the joint autocorrelation is not significant
    But given a series of AR(1) returns
    When I run the Ljung-Box test
    Then the joint autocorrelation is significant

  Scenario: Variance-Ratio test for random walk
    Given a random walk price series
    When I run the variance-ratio test
    Then the variance-ratio is close to 1.0
    And the state verdict is "random walk"
    And the returned window type is "overlapping"

  Scenario: Bootstrap confidence intervals for skewness and kurtosis
    Given a returns series of standard normal returns
    When I run the bootstrap distribution uncertainty test
    Then the confidence intervals contain the point estimates of skewness and kurtosis
    And the results are reproducible across multiple calls with the same seed

  Scenario: Configurable period and sufficiency check
    Given a daily price series that has fewer than 750 bars
    When I check for data sufficiency
    Then a sufficiency warning is returned
