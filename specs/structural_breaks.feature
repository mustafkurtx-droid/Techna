Feature: Structural Break Detection
  Scenario: Volatility regime shift detection
    Given a series with a significant volatility regime shift in the middle
    When I run the structural break detection
    Then the detector locates the break point within a tolerance window of the actual shift index
    And the detected break type is "volatility_shift"

  Scenario: Mean regime shift detection
    Given a series with a significant mean shift in the middle
    When I run the structural break detection
    Then the detector locates the break point within a tolerance window of the actual shift index
    And the detected break type is "mean_shift"

  Scenario: No breaks on a homogeneous series
    Given a homogeneous IID series with no regime shifts
    When I run the structural break detection
    Then no structural breaks are detected

  Scenario: Parameter stability CUSUM test
    Given a series with a structural break in the middle
    When I run the OLS residuals CUSUM parameter stability test
    Then the CUSUM test flags the series as unstable
