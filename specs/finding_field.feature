Feature: JSON sidecar carries a plain-English finding per module
  Scenario: Each module's JSON metrics include a one-line finding
    Given a completed Techna run for a valid ticker
    When I read the {TICKER}_result.json sidecar
    Then every module's metrics dict contains a non-empty "finding" string
    And the finding matches the corresponding sentence in the markdown report

  Scenario: A module with insufficient data still yields a safe finding
    Given a ticker with too little history for a given module
    When the JSON sidecar is written
    Then that module's finding is a short fallback sentence, never empty or null

  Scenario: Findings never contain advice language
    Given any computed finding string
    When it is checked against the advisor guardrail
    Then it contains no "buy", "sell", or "hold" token
