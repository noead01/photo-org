# Issue 38 Facet Filters Design

## Summary

Issue `#38` should add the first explicit facet-style search filter slice to the current Phase 3 search implementation. The scope should stay narrow: support path-hint filtering and boolean face-presence filtering in the request contract, and expose a `has_faces` facet breakdown over the filtered result set.

## Goals

- Add a request-level filter for path-derived hints without reopening the full text-search design.
- Preserve and tighten `has_faces` filtering semantics for both `true` and `false`.
- Expose a `has_faces` facet result so callers can inspect the filtered set's face-bearing versus no-face breakdown.
- Keep the change aligned with the current search service and repository architecture.

## Non-Goals

- Redesign the full search DSL or transport contract.
- Add people or geo facet families beyond what already exists.
- Introduce separate indexing infrastructure for path hints.
- Expand the seed corpus.

## Design Decisions

### Path hints are explicit filters, not free-text fallback

The Phase 3 scenario catalog distinguishes text search from typed filters. For `#38`, path hints should be modeled as an explicit `SearchFilters.path_hints` field rather than folded into `q`. This keeps path-derived filtering composable with text search and other typed filters.

### Path hints derive from the existing canonical photo path

The implementation should derive path-hint matching from `photos.path`, using substring matching over normalized hint tokens. This is sufficient for the current seed-corpus-backed Phase 3 slice and avoids introducing a separate stored hint table.

### `has_faces` remains a boolean filter and becomes a boolean facet

`has_faces` already exists as a filter field and now supports `true` and `false`. `#38` should extend the facet output so clients can ask "within this filtered set, how many photos have faces and how many do not?" The facet should be returned alongside the existing `date`, `people`, `tags`, and `duplicates` facets.

## Expected Request Contract

Within the current schema, add:

- `filters.path_hints: list[str] | null`

Meaning:

- values combine with `ANY` semantics within the field
- path-hint filtering combines with all other filter families using `AND`

Example:

```json
{
  "filters": {
    "path_hints": ["lake-weekend"],
    "has_faces": false
  }
}
```

## Expected Response Contract

Extend the facet payload with:

- `facets.has_faces`

Recommended shape:

```json
{
  "true": 4,
  "false": 2
}
```

This is intentionally narrow and should be computed over the filtered result set, not the whole corpus.

## Test Strategy

Add coverage at the search repository and search service layer for:

- filtering by a single path hint
- combining path hints with `has_faces`
- returning the `has_faces` facet breakdown for filtered photo IDs
- ensuring the seed-corpus-backed search fixtures remain valid after the schema change

## Risks And Constraints

- The current search implementation centralizes filtering in `PhotosRepository._apply_filters`, so `#38` will share files with later search issues.
- Path matching should avoid pretending to be a full tokenizer; keep the behavior simple and documented.
- Facet output changes should remain backward-compatible with the current search response shape conventions.
