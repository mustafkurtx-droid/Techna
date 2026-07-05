Feature: Drawdown Analysis
  Scenario: Drawdown series calculation matches running max
    Given a price history
    When I calculate drawdown series
    Then drawdown at each index equals (close - running_max) / running_max

  Scenario: Drawdown episode peak, trough, and recovery dates match episodes
    Given a price history with distinct peaks and troughs
    When I identify drawdown episodes
    Then each episode reports peak_date as the last peak before drawdown started
    And trough_date as the date of maximum drawdown severity
    And recovery_date as the first date the price recovered to or exceeded the peak

  Scenario: Unrecovered episode has no recovery date
    Given a price history that does not recover after a peak
    When I identify drawdown episodes
    Then the recovery_date for the unrecovered episode is None
    And days_to_recover is None
