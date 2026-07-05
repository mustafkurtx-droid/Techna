Feature: Relative strength vs a benchmark
  As Techna, I want to evaluate the relative strength of an asset compared to a benchmark index
  to show if the asset is outperforming or underperforming the market.

  Scenario: Asset and benchmark are aligned on common dates
    Given an asset price series with dates
    And a benchmark price series with different dates
    When I align their closes
    Then only the dates present in both series are kept
    And the aligned closes have the exact same index length and order

  Scenario: Relative strength is the ratio of asset to benchmark
    Given aligned asset and benchmark close price series
    When I calculate their relative strength
    Then the relative strength series at index t equals asset[t] / benchmark[t]

  Scenario: Rebased performance starts at 100 for both series
    Given aligned close price series
    When I calculate the rebased performance
    Then the rebased series starts at exactly 100 at the first date
    And each value is close[t] / close[0] * 100

  Scenario: rs_state reflects whether the asset is out/under-performing
    Given a relative strength ratio series
    And its SMA moving average
    When I compute the rs_state
    Then the state is "outperforming" if RS > RS_MA and RS is increasing (RS[t] > RS[t-1])
    And the state is "underperforming" if RS < RS_MA and RS is decreasing (RS[t] < RS[t-1])
    And the state is "neutral" otherwise

  Scenario: A missing benchmark degrades gracefully with a warning
    Given a missing benchmark ticker
    When I run the CLI orchestrator
    Then the benchmark fetch fails and displays a warning
    And the orchestrator completes successfully with exit code 0
