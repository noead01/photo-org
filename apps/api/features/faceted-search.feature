Feature: Faceted search API
  Background:
    Given a photo library with photos, faces, tags, and EXIF loaded
    And the search endpoint is available at "/api/v1/search"

  # --- Happy paths ---
  @happy-path
  Scenario: Happy path — multiple filters and default sorting
    When I search with
      | q              | |
      | date.from      | 2020-01-01 |
      | date.to        | 2020-12-31 |
      | camera_make    | Apple |
      | extension      | heic |
      | has_faces      | true |
      | tags           | ["vacation"] |
      | people         | ["person_ines"] |
      | sort.by        | shot_ts |
      | sort.dir       | desc |
      | page.limit     | 50 |
    Then every hit has ext in ["heic"] and camera_make in ["Apple"]
    And every hit has shot_ts within [2020-01-01, 2020-12-31]
    And every hit contains at least one face
    And every hit contains tag "vacation"
    And at least one hit contains person "person_ines"
    And hits are sorted by shot_ts desc then photo_id
    And the response includes facets computed from the filtered result set

  Scenario: Happy path — no filters returns newest photos first
    When I search with empty filters and page.limit 60
    Then I receive at most 60 hits
    And hits are sorted by shot_ts desc then photo_id
    And the total is >= hits length

  Scenario: Conjunctive across facets narrows results
    Given current filters tags ["vacation"]
    When I also filter by camera_make ["Apple"] and orientation ["landscape"]
    Then results only include photos that have tag "vacation" AND camera_make "Apple" AND orientation "landscape"

  Scenario: Disjunctive within a facet (tags)
    Given current filters tags ["beach"]
    When I also select tag "sunset" in the same facet
    Then results include photos that have tag "beach" OR tag "sunset" (or both)

  Scenario: Disjunctive within a facet (people)
    Given current filters people ["person_ines"]
    When I also select person "person_john"
    Then results include photos where person_ines OR person_john appear

  # --- Facet correctness (drill-sideways) ---
  Scenario: Drill-sideways counts for tags exclude the tag filter itself
    Given current filters tags ["beach"] and camera_make ["Apple"]
    When I view the tags facet
    Then the count for a tag value T is computed as if camera_make ["Apple"] is applied AND the tags filter is removed

  Scenario: People facet counts use distinct photo IDs
    Given a photo with two faces both linked to person_ines
    When I view the people facet with filters that include that photo
    Then the count for person_ines increases by 1 (not 2)

  Scenario: Date hierarchy sums are consistent
    When I select year 2020 in the date facet
    Then the sum of all month buckets in 2020 equals the 2020 year bucket
    And selecting a month shows day buckets that sum to the month bucket

  Scenario: Duplicates facet shows exact and near-duplicate totals
    Given at least one sha256 group of size > 1 and near-duplicate phash groups
    When I request the duplicates facet
    Then the response includes an "exact" integer > 0 and a "near" integer >= 0

  # --- Pagination & cursors ---
  Scenario: Pagination with opaque cursor has no duplicates
    When I request page.limit 60 sorted by shot_ts desc and receive cursor C1
    And I request the next page with cursor C1
    Then there are no duplicate photo_ids between the two pages

  Scenario: Cursor stability with tiebreaker
    Given at least two photos share the same shot_ts
    When I paginate
    Then ordering uses (shot_ts, photo_id) to break ties and pagination remains deterministic

  # --- Search modalities ---
  Scenario: Trigram text query influences relevance sort
    When I search with q = "hawaii beach"
    And sort.by = "relevance"
    Then hits include photos whose path or tags are trigram-similar to the query
    And relevance scores are non-increasing

  Scenario: Vector similarity with additional filters
    When I pass a 128-dim vector and similarity_k 40 and tags ["portrait"]
    Then all hits are among the 40 nearest neighbors by vector distance
    And every hit contains tag "portrait"

  # --- Edge cases & errors ---
  Scenario: Empty result set
    When I filter on a future date range with no photos
    Then the response has total 0 and hits.items is empty
    And all facets are empty or zero-count as applicable

  Scenario: Invalid request is rejected
    When I pass more than 100 values in the tags filter
    Then I receive an error with code "BAD_REQUEST"

  Scenario Outline: Filesize bucket mapping
    When I filter on filesize_range <range>
    Then all hits have filesize within the configured bounds for <range>
    Examples:
      | range   |
      | small   |
      | medium  |
      | large   |
