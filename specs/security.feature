Feature: Dependency provenance (slopsquatting defense)
  As Techna, I must never install a package that does not genuinely exist on
  PyPI, and only packages from a curated allowlist, to defend against
  hallucinated or typosquatted package names.

  Scenario: Requirements only contain approved packages
    Given the requirements file
    When I parse the required package names
    Then every package is on the curated allowlist
    And there are no duplicate packages

  Scenario: Active PyPI existence check before install
    Given the list of required packages
    When I query PyPI for each name
    Then each package resolves to an existing project
    And setup aborts non-zero if any name is missing or unapproved
