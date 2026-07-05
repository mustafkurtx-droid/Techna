Feature: Stationarity Analysis (ADF + KPSS)
  Scenario: Random walk series is non-stationary
    Given a simulated random walk series
    When I run the stationarity tests
    Then the ADF test fails to reject the null hypothesis of non-stationarity
    And the KPSS test rejects the null hypothesis of stationarity
    And the combined verdict is "non-stationary (unit root / random walk)"

  Scenario: Mean-reverting series is stationary
    Given a simulated mean-reverting stationary series
    When I run the stationarity tests
    Then the ADF test rejects the null hypothesis of non-stationarity
    And the KPSS test fails to reject the null hypothesis of stationarity
    And the combined verdict is "stationary"

  Scenario: Combined verdict decision matrix
    Given mock pvalues for ADF and KPSS
    When I compute the combined verdict
    Then the output verdict matches the decision matrix rules:
      | adf_p  | kpss_p | verdict                                       |
      | 0.01   | 0.08   | stationary                                    |
      | 0.25   | 0.01   | non-stationary (unit root / random walk)      |
      | 0.02   | 0.03   | difference-stationary / possibly fractional   |
      | 0.30   | 0.12   | inconclusive / trend-stationary               |
