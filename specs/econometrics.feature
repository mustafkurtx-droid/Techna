Feature: Econometric analysis (ACF/PACF & return distribution)
  As Techna, I want to calculate econometric statistics
  to identify serial correlation (predictability), volatility clustering, and return distribution normality/fat-tailed characteristics.

  Scenario: ACF matches an independent direct-formula computation at early lags
    Given a log return series
    When I calculate ACF
    Then the calculated ACF values at lag 1 and lag 2 match the direct-formula correlation

  Scenario: PACF at lag 1 equals ACF at lag 1
    Given a log return series
    When I calculate ACF and PACF
    Then the value of PACF at lag 1 equals the value of ACF at lag 1

  Scenario: Volatility clustering is detected when squared returns autocorrelate early
    Given a return series with clusters of high and low volatility
    When I calculate ACF of squared returns
    Then the squared returns show significant positive autocorrelation at early lags
    And the volatility clustering flag is True

  Scenario: No clustering is flagged for an i.i.d. return series
    Given an i.i.d. random return series
    When I calculate ACF of squared returns
    Then the squared returns do not show significant positive autocorrelation at early lags
    And the volatility clustering flag is False

  Scenario: Raw-returns autocorrelation uses the same early-lag discipline as clustering
    Given a return series
    When I check raw-returns autocorrelation
    Then only the early lags are considered (not a full multiple-comparison scan)
    And an i.i.d. series is reported as no autocorrelation (random walk)
    And a strongly autocorrelated series is flagged as detected

  Scenario: Skewness and excess kurtosis match independent moment formulas
    Given a sample return series
    When I calculate skewness and excess kurtosis
    Then the results match the values computed via sample moment definitions (bias=True, fisher=True)

  Scenario: Jarque-Bera matches an independent computation from skew/kurtosis
    Given a sample return series
    When I calculate Jarque-Bera statistic
    Then the statistic equals n/6 * (skewness^2 + 0.25 * excess_kurtosis^2)

  Scenario: A fat-tailed series is reported as not consistent with Normal
    Given a return series containing extreme outliers (fat tails)
    When I check for normality via Jarque-Bera p-value
    Then the p-value is less than 0.05
    And the normality flag is False
