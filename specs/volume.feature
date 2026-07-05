Feature: Volume analysis (OBV & VWAP)
  As Techna, I want to calculate Volume metrics (OBV & VWAP)
  to identify volume-based momentum, price/volume divergence, and average trade price value.

  Scenario: OBV adds volume on up days, subtracts on down days, holds when unchanged
    Given a closing price series and a volume series
    When I calculate OBV
    Then the first value of OBV is 0
    And for each subsequent day:
      | price change | OBV change |
      | positive     | + volume   |
      | negative     | - volume   |
      | zero         | unchanged  |

  Scenario: OBV divergence flags bullish when price falls but OBV rises
    Given a closing price series showing a negative slope
    And an OBV series showing a positive slope
    When I detect OBV divergence
    Then the state is bullish_divergence

  Scenario: OBV divergence flags bearish when price rises but OBV falls
    Given a closing price series showing a positive slope
    And an OBV series showing a negative slope
    When I detect OBV divergence
    Then the state is bearish_divergence

  Scenario: OBV confirms when price and OBV move the same way
    Given a closing price series and OBV series with slopes of the same sign
    When I detect OBV divergence
    Then the state is confirming

  Scenario: Full VWAP equals cumulative(tp*vol)/cumulative(vol)
    Given a high, low, close, and volume series
    When I calculate cumulative VWAP
    Then the value equals cumulative(typical_price * volume) / cumulative(volume)

  Scenario: Rolling VWAP has a warm-up of period-1 NaNs
    Given a high, low, close, and volume series
    When I calculate rolling VWAP with period N
    Then the first N-1 values of rolling VWAP are NaN

  Scenario: Price-vs-VWAP state is above/below with a percentage distance
    Given a closing price and a VWAP value
    When I check VWAP state
    Then the state is above_vwap if close > vwap else below_vwap
    And the distance percentage is (close - vwap) / vwap * 100
