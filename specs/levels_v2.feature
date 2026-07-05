Feature: Support/resistance significance filter (levels v2)
  As Techna, I want to filter support and resistance levels by clustering nearby pivots
  and selecting only the most significant ones, while avoiding lookahead bias by excluding unconfirmed pivots.

  Scenario: Nearby pivots within tolerance collapse into one level
    Given a list of pivot prices
    And a tolerance threshold
    When I cluster the pivot prices
    Then pivots that are close to each other are merged into a single cluster representing their average price

  Scenario: A level's strength equals the number of pivots that formed it
    Given a list of pivot prices
    When I cluster them
    Then each cluster has a "touches" count matching the number of members in it

  Scenario: Only the top-N strongest levels are kept
    Given a list of clusters
    When I rank and filter them with top_n = 2
    Then at most 2 clusters are returned
    And they are the ones with the highest touches count

  Scenario: An extreme within the last k bars is never reported as a level
    Given a price series with a sharp extreme on the last bar
    When I select levels
    Then that extreme is not reported as a confirmed level
    Because a pivot only exists where its full +/-k window is available

  Scenario: Levels are ranked by strength deterministically
    Given a list of clusters with equal touches count
    When I rank them
    Then they are ordered deterministically by price in descending order
