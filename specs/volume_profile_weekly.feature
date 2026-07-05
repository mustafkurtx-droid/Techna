Feature: Weekly Volume Profile
  Scenario: Volume profile is computed on weekly resampled bars
    Given a daily price series spanning 10 weeks
    When weekly volume profile is computed
    Then weekly bars are used in calculation
    And the final daily close is compared to the weekly value area VAL and VAH
