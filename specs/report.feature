Feature: Report generation
  As Techna, I need to generate comprehensive markdown reports and visual charts
  so that humans can inspect indicator conditions with a warning disclaimer.

  Scenario: A markdown report file is created at the returned path
    Given a ticker and analysis results
    When I trigger report generation
    Then a markdown file is written to the reports directory
    And the returned path exists on disk

  Scenario: The report contains a section for each computed indicator
    Given a generated report file
    When I inspect its content
    Then it contains sections for SMA, EMA, MACD, RSI, and Bollinger Bands

  Scenario: The report states it provides signals, not advice
    Given a generated report file
    When I inspect its content
    Then it contains a prominent notice stating "signals, not advice" or similar warning

  Scenario: The chart image is written to the reports directory
    Given a ticker and price series
    When I trigger report generation with chart drawing enabled
    Then a PNG chart file is saved to the reports directory
    And the chart contains subplots for prices, RSI, and MACD
