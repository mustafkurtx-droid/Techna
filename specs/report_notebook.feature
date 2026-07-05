Feature: Static report presentation notebook generation
  Scenario: Running with --notebook generates a static .ipynb file
    Given a completed Techna run with --notebook
    When I read the output directory
    Then a {TICKER}_report.ipynb file is created
    And the notebook contains only markdown cells
    And the notebook contains no code cells
    And the notebook includes plain-English findings from the result JSON
    And the notebook embeds the generated PNG chart files via markdown image links
