Feature: Techna orchestrator
  As Techna, I need a main command-line orchestrator that coordinates data fetching,
  indicator calculation, terminal reporting, and markdown/chart report compilation.

  Scenario: Running a valid ticker produces a report and exit code 0
    Given a valid ticker
    When I run the orchestrator tool
    Then it fetches the prices
    And computes all indicators (trend, momentum, volatility, levels)
    And writes the report files to the reports directory
    And prints a Rich panel dashboard to the terminal
    And exits with code 0

  Scenario: An invalid ticker fails gracefully with a friendly message and code 1
    Given an invalid or delisted ticker
    When I run the orchestrator tool
    Then it print a friendly data error message to the terminal without traceback
    And exits with code 1

  Scenario: Insufficient history for SMA200 is reported as a warning, not a crash
    Given a ticker with only 40 days of history
    When I run the orchestrator tool requiring SMA200 calculation
    Then it records warnings in the results
    And completes the other calculations gracefully
    And prints warnings to the terminal
    And exits with code 0

  Scenario: --no-interactive runs end-to-end without prompting
    Given the CLI is triggered with --no-interactive
    When the orchestrator executes
    Then it completes all calculations and writes reports without asking for human confirmations
