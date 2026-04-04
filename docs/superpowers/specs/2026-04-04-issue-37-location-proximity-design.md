# Issue 37 Design: Location Filtering And Proximity Search

## Summary

Issue #37 adds coordinate-based proximity filtering to the existing search API.
The search contract will accept a typed `location_radius` filter with `latitude`, `longitude`, and an optional `radius_km`.
If `radius_km` is omitted, the API defaults it to `50`.
The API rejects invalid coordinates and non-positive radius values with clear validation errors.
When a location filter is present, photos without GPS coordinates are excluded.

## Goals

- Support coordinate-based proximity search through the existing search request contract.
- Keep the issue scoped to typed latitude/longitude input with an optional radius.
- Exclude non-geotagged photos whenever a location filter is active.
- Add automated coverage for request validation and repository filtering behavior.

## Non-Goals

- Place-name search such as "near Paris".
- Geocoding or reverse geocoding.
- Geographic region inference such as countries, cities, or landmarks.
- Ranking or relevance changes beyond existing search sort behavior.
- UI workflows for choosing coordinates.

## Existing Context

The current search stack already supports typed filters such as date, people, path hints, and camera make.
The Phase 3 search scenario catalog already reserves `location_radius` and identifies coordinate-based proximity as the minimum viable geo predicate for Phase 3.
The repository already stores canonical photo GPS fields on `photos.gps_latitude` and `photos.gps_longitude`, so the first delivery slice can stay within the current schema and repository surfaces.

## Proposed Contract

The existing `SearchFilters` model gains an optional `location_radius` field:

```text
filters:
  location_radius:
    latitude: <float>
    longitude: <float>
    radius_km: <float, optional, default 50>
```

Validation rules:

- `latitude` is required when `location_radius` is present and must be between `-90` and `90`.
- `longitude` is required when `location_radius` is present and must be between `-180` and `180`.
- `radius_km` defaults to `50` when omitted.
- `radius_km` must be greater than `0`.
- Invalid payloads fail at the API schema boundary with helpful 422 validation messages.

## Search Semantics

When `location_radius` is present:

- only photos with both `gps_latitude` and `gps_longitude` are eligible
- distance is measured from the request coordinate to the photo coordinate
- a photo matches when its computed distance is less than or equal to the requested radius
- the location predicate composes with all other filters using the same `AND` semantics as the rest of the search contract

The implementation should not silently approximate unsupported user intent.
If the caller wants place-based search, that belongs to a future geocoding-oriented slice, not this issue.

## Repository Design

The repository implementation stays in the existing search query builder.
`PhotosRepository._apply_filters()` should append a geo predicate only when `filters.location_radius` is present.

The predicate should:

- require non-null GPS coordinates on the photo row
- compute spherical distance from the request point
- compare the computed distance to the radius in kilometers

For this slice, an inline SQL expression is sufficient.
The design does not require a migration, PostGIS, or a new helper table.
The query should remain portable across the project’s current database-backed test workflows.

## Error Handling

Invalid geo filters are request-contract failures, not repository-level soft failures.
The API should surface those failures through the normal FastAPI and Pydantic validation response path so callers get actionable error details without ambiguous empty-result behavior.

## Testing Strategy

Add test coverage in the existing search test suite for:

- accepting `location_radius` without `radius_km` and using the default radius
- matching only photos within a requested explicit radius
- excluding photos that have null GPS coordinates when the location filter is present
- combining location filtering with another existing filter to confirm `AND` semantics
- rejecting invalid latitude values
- rejecting invalid longitude values
- rejecting zero or negative `radius_km`

The repository tests should continue to use the current temporary database fixture pattern already used by the search suite.

## Documentation Impact

Developer-facing documentation should be updated only where the search contract or verification examples need to mention coordinate-based filtering.
No user-facing geocoding language should be introduced, because that would imply broader scope than this issue delivers.

## Verification

The implementation should be verified with focused automated tests for the search schema and repository behavior, plus the normal repo test slice used for search-related work.

## Open Questions Resolved

- Scope remains coordinate-based only.
- Photos without GPS coordinates are excluded when the filter is present.
- `radius_km` is optional and defaults to `50`.
- Invalid input is rejected by the API with helpful validation errors.
