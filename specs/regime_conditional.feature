Feature: Regime-Conditional Statistics
  Scenario: Returns series with no breaks uses full sample
    Given a returns series with no structural breaks detected
    When I compute the regime-conditional statistics
    Then the status flag is_split is false
    And the regime statistics are identical to the full sample statistics
    And the regime_too_short flag is false

  Scenario: Returns series with breaks computes split statistics
    Given a returns series with a structural break in the middle
    When I compute the regime-conditional statistics
    Then the status flag is_split is true
    And the regime start date matches the last break date
    And the regime statistics represent only the post-break segment
    And the regime_too_short flag is false

  Scenario: Break occurs too close to the end of the series
    Given a returns series with a structural break very close to the end
    When I compute the regime-conditional statistics
    Then the status flag is_split is true
    And the regime_too_short flag is true
