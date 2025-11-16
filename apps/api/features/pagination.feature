Feature: Pagination and cursor functionality
  Background:
    Given a photo library with photos, faces, tags, and EXIF loaded
    And the search endpoint is available at "/api/v1/search"

  Scenario: Basic cursor pagination works correctly
    When I request the first page with limit 5
    And I use the returned cursor to get the next page
    Then the second page contains different photos than the first
    And the photos are in correct sort order across pages

  Scenario: Cursor pagination maintains sort order
    When I paginate through results sorted by shot_ts ascending
    Then each subsequent page maintains ascending timestamp order
    And no timestamps go backwards between pages

  Scenario: Cursor pagination with filters
    When I apply tag filter "vacation" and paginate with limit 3
    Then all pages contain only photos with "vacation" tag
    And pagination works correctly with the filter applied

  Scenario: Empty cursor returns first page
    When I request search with empty cursor
    Then I receive the first page of results
    And the response is identical to a request without cursor

  Scenario: Cursor from different sort order is invalid
    When I get a cursor from results sorted by shot_ts descending
    And I use that cursor with sort by shot_ts ascending
    Then I receive an appropriate error or warning
    And the system handles the inconsistency gracefully

  Scenario: Page limit variations
    When I request pages with limits 1, 10, 50, and 100
    Then each request returns the correct number of results
    And cursors work correctly across different page sizes

  Scenario: Cursor stability across identical requests
    When I make the same search request twice
    Then both requests return identical cursors for the same position
    And the cursors can be used interchangeably

  Scenario: Large dataset pagination performance
    When I paginate through a large result set
    Then each page request completes in reasonable time
    And memory usage remains stable across pages