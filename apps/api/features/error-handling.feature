Feature: Error handling and edge cases
  Background:
    Given a photo library with photos, faces, tags, and EXIF loaded
    And the search endpoint is available at "/api/v1/search"

  Scenario: Invalid cursor format returns error
    When I request search with invalid cursor "invalid_cursor_format"
    Then I receive a 400 error response
    And the error message indicates invalid cursor format

  Scenario: Malformed JSON request returns validation error
    When I send a malformed JSON request to the search endpoint
    Then I receive a 422 validation error
    And the response includes validation details

  Scenario: Empty filters with various sort options
    When I search with empty filters and sort by "shot_ts" direction "asc"
    Then I receive results sorted by shot_ts ascending
    And all results have valid shot_ts values

  Scenario: Large page limit is capped
    When I request search with page limit 10000
    Then I receive at most 1000 results
    And the response indicates the limit was capped

  Scenario: Zero page limit returns default results
    When I request search with page limit 0
    Then I receive the default number of results
    And the page limit in response reflects the default

  Scenario: Invalid date format in filters
    When I search with invalid date format "not-a-date" in date filter
    Then I receive a 422 validation error
    And the error indicates invalid date format

  Scenario: Boundary date values
    When I search with date from "1900-01-01" to "2100-12-31"
    Then I receive results within the valid date range
    And no results fall outside the specified boundaries

  Scenario: Special characters in text query
    When I search with query containing special characters "photo@#$%^&*()"
    Then the search completes without error
    And results are returned or empty set is valid

  Scenario: Very long tag names in filters
    When I search with a tag filter containing very long tag name
    Then the search handles long tag names gracefully
    And returns appropriate results or empty set

  Scenario: Multiple identical filters
    When I search with duplicate tag filters ["beach", "beach", "sunset"]
    Then the search deduplicates the filters
    And results match the unique set of tags

  Scenario: Cursor pagination at dataset boundaries
    When I paginate through all results using cursors
    Then I eventually reach the end of the dataset
    And the final page has no cursor for next page
    And no results are duplicated across pages