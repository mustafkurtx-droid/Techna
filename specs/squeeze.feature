Feature: Bollinger Squeeze and Daily Events
  Scenario: Squeeze starts when Bollinger bands compression enters Keltner channels
    Given a series where squeeze was False and changes to True on the last bar
    When event detection is run
    Then an event of type "squeeze_start" with direction "neutral" is detected

  Scenario: Squeeze release occurs when Bollinger bands break out of Keltner channels
    Given a series where squeeze was True and changes to False on the last bar
    When event detection is run
    Then an event of type "squeeze_release" with direction "neutral" is detected

  Scenario: Squeeze duration increases consecutively
    Given a series where squeeze is active for the last 5 bars
    When squeeze indicator is computed
    Then the squeeze duration is 5
