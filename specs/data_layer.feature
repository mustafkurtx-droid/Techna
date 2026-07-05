Feature: Shared price data layer
  As Techna, I need a single cached source of OHLCV price data so that
  every indicator module reads identical data and the network is contacted
  at most once per ticker.

  Background:
    Given a clean cache directory
    And a deterministic golden price fixture of 40 trading days

  Scenario: Fetch once, then reuse from cache
    Given no cached data exists for "TEST"
    When I request prices for "TEST"
    Then the prices are returned with source "fixture"
    And a cache file for "TEST" is written to disk
    When I request prices for "TEST" again
    Then the prices are returned with source "cache"
    And the fetcher is not called

  Scenario: Invalid or delisted ticker
    Given the fetcher returns no rows for "BADTICK"
    When I request prices for "BADTICK"
    Then an InvalidTickerError is raised
    And the message explains the ticker may be invalid or delisted

  Scenario: Network disabled with an empty cache
    Given no cached data exists for "TEST"
    And network access is disabled
    When I request prices for "TEST"
    Then a NetworkError is raised

  Scenario: Insufficient history for the requested computation
    Given prices for "TEST" containing 40 rows
    When a caller requires at least 200 rows
    Then an InsufficientDataError is raised

  Scenario: Duplicate timestamps are deduplicated
    Given the fetched data contains two rows with the same timestamp
    When I request prices for "TEST"
    Then only the last occurrence of the duplicated timestamp is kept
    And a warning reports how many duplicate rows were dropped

  Scenario: Non-positive prices are rejected
    Given the fetched data contains a row with a zero or negative price
    When I request prices for "TEST"
    Then that row is dropped from the result
    And a warning explains that non-positive prices would corrupt log returns

  Scenario: Rows with missing price values
    Given the fetched data contains a row with no price values
    When I request prices for "TEST"
    Then that row is dropped from the result
    And a warning reports how many rows were dropped

  Scenario: Canonical schema and ordering
    When I request prices for any ticker
    Then the columns are exactly Open, High, Low, Close, Volume
    And the rows are sorted by ascending date
