Feature: 52-Week Range Position
  Scenario: Position percent matches math relative to min and max of window
    Given a closing price series
    When I compute the 52-week range position
    Then the position percent equals (current - min) / (max - min) * 100

  Scenario: State classification near high
    Given a closing price series near its 52-week high (position >= 90%)
    When I compute the 52-week range position
    Then the state is near_52w_high

  Scenario: State classification near low
    Given a closing price series near its 52-week low (position <= 10%)
    When I compute the 52-week range position
    Then the state is near_52w_low

  Scenario: State classification mid range
    Given a closing price series in the middle of its 52-week range
    When I compute the 52-week range position
    Then the state is mid_range

  Scenario: Zero range returns NaN and mid range
    Given a flat closing price series (max equals min)
    When I compute the 52-week range position
    Then the position percent is NaN
    And the state is mid_range
