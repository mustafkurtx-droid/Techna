Feature: Analyst Briefing Synthesis
  Scenario: Briefing is generated deterministically
    Given computed indicators and scores
    When I generate the analyst briefing
    Then the output is a formatted string briefing
    And the mandatory disclaimer is appended at the end

  Scenario: Confirmations are reported when indicators align
    Given a strong trend score and bullish momentum score
    When I generate the analyst briefing
    Then the briefing reports confirmations of indicator alignment

  Scenario: Contradictions are reported when indicators clash
    Given high momentum score but extended trend maturity score
    When I generate the analyst briefing
    Then the briefing reports contradictions highlighting the extended maturity

  Scenario: Asset vs Textbook comparison
    Given active setup matching an empirical base rate with sufficient samples
    When I generate the analyst briefing
    Then the briefing includes the asset vs textbook comparison sentence
    And it shows the historical win rate and sample count

  Scenario: Asset vs Textbook comparison is skipped on low samples
    Given active setup matching an empirical base rate with small samples (n < limit)
    When I generate the analyst briefing
    Then the asset vs textbook comparison is omitted due to insufficient samples

  Scenario: Guardrail prohibits advisory advice
    Given any indicators and scores
    When I generate the analyst briefing
    Then the output briefing does not contain advising tokens like buy, sell, or hold
