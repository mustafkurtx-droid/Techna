Feature: Volume Profile (VP) and Value Area (VA)
  Scenario: Volume of a bar is distributed proportionally across price bins
    Given a bar with High 28, Low 12, and Volume 100
    When volume profile is computed with 3 bins: 10-20, 20-30, 30-40
    Then Bin 0 has 50 volume
    And Bin 1 has 50 volume
    And Bin 2 has 0 volume

  Scenario: Single price bar allocates 100% volume to its containing bin
    Given a bar with High 15, Low 15, and Volume 150
    When volume profile is computed with 3 bins: 10-20, 20-30, 30-40
    Then Bin 0 has 150 volume
    And Bin 1 has 0 volume

  Scenario: Value Area is expanded from POC resolving tie-breaks
    Given a volume profile with POC at index 1 and equal volumes at indices 0 and 2
    When Value Area expansion is executed
    Then the upper index 2 is expanded first before the lower index 0
