Feature: Seasonality / monthly-return heatmap
  As Techna, I want to calculate monthly return seasonality distributions
  to present calendar monthly returns and statistics to the user in a visual heatmap.

  Scenario: Monthly returns use month-end closes
    Given a daily closing price series spanning multiple months
    When I calculate monthly returns using resample("ME")
    Then the return for each month t is close[month_end_t] / close[month_end_t-1] - 1

  Scenario: The seasonality table is indexed by year and month
    Given a monthly returns series
    When I pivot the returns into a seasonality table
    Then the table's index is the year
    And the table's columns are the calendar months 1 to 12
    And cells represent the respective monthly returns

  Scenario: The monthly summary reports an average return per calendar month
    Given a monthly returns series
    When I calculate the monthly summary
    Then I get the average return for each calendar month (1 to 12)
    And I get the win rate (percentage of positive returns) for each calendar month

  Scenario: Insufficient history (under a year) is flagged
    Given a price series spanning fewer than 12 months (under a year)
    When I analyze seasonality
    Then the analysis raises an InsufficientDataError or returns an empty result with a warning
