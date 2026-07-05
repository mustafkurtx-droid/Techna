Feature: Empirical base rates (descriptive, not predictive)
  As Techna, I want to calculate the historical forward return distributions of an asset
  conditioned on technical events, to show the empirical baseline probability distributions.

  Scenario: Forward returns shift price by the horizon and tail is NaN
    Given a closing price series
    And a forward horizon N
    When I compute the forward return
    Then the forward return series at index t equals close[t + N] / close[t] - 1
    And the last N values of the forward return series are NaN

  Scenario: Conditional stats summarise only the bars where the condition holds
    Given a boolean condition series
    And a forward return series
    When I compute the conditional stats
    Then only the rows where the condition is True are evaluated for stats (n, mean, median)

  Scenario: Win rate is the share of positive forward returns
    Given a list of forward returns under a condition
    When I compute the win rate
    Then the win rate is the count of strictly positive returns divided by the total count of non-NaN returns under the condition

  Scenario: A small sample is flagged as not reliable
    Given a condition that occurs fewer times than min_sample
    When I compute the conditional stats
    Then the "reliable" flag is False

  Scenario: Baseline stats use all bars
    Given a forward return series
    When I compute the baseline stats
    Then all non-NaN bars are evaluated for the return stats
