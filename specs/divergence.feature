Feature: Price/oscillator divergence
  As Techna, I need to detect divergence between price and a momentum
  oscillator (RSI/MACD), using only confirmed swing points, so that I never
  claim a divergence on still-forming bars (no look-ahead). Divergence is a
  reported state, not advice.

  Scenario: Bearish divergence
    Given a price series making a higher swing high
    And an oscillator making a lower swing high at those swings
    When I detect divergence
    Then a bearish divergence is reported
    And no bullish divergence is reported

  Scenario: Bullish divergence
    Given a price series making a lower swing low
    And an oscillator making a higher swing low at those swings
    When I detect divergence
    Then a bullish divergence is reported

  Scenario: No divergence when price and oscillator agree
    Given a price series and oscillator that move together
    When I detect divergence
    Then neither bullish nor bearish divergence is reported

  Scenario: Swing points near the edges are not confirmed
    Given a price series
    When I find swing points with window k
    Then no swing is reported within k bars of either end
