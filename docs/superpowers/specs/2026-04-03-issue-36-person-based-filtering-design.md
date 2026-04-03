# Issue 36 Person-Based Filtering Design

## Summary

Issue `#36` should add person-based filtering to the current Phase 3 search surface by allowing callers to filter photos with fuzzy name matching against labeled people. The scope should stay narrow: add an explicit request field for person-name queries, resolve those queries against stored person identities, and apply the filter through the existing search repository path.

## Goals

- Add a typed search filter for fuzzy person-name matching.
- Keep the change aligned with the current `SearchRequest` and `PhotosRepository` architecture.
- Make person-name filtering compose cleanly with existing text, date, path-hint, tag, and face-presence filters.
- Cover the new behavior with automated tests at the repository and search-service layer.

## Non-Goals

- Redesign the full search DSL.
- Introduce a separate fuzzy-search index or ranking system for people.
- Change the search response payload to expose person display names.
- Implement exact `person_id` filtering semantics beyond preserving the existing field.

## Design Decisions

### Person-name filtering is a typed filter, not free text

The search request should gain a dedicated `filters.person_names` field rather than folding person matching into top-level `q`. This keeps person filtering explicit, composable with other filter families, and consistent with the existing typed-filter direction established by date and path-hint filtering.

### `filters.people` remains reserved for exact identifiers

The existing `filters.people` field should not be repurposed to mean fuzzy names. Its name already implies exact person identifiers, and overloading it now would create avoidable ambiguity when exact ID filtering is implemented later. For this issue, the new behavior belongs in `filters.person_names`.

### Matching resolves against `people.display_name`

The filter should resolve against the canonical person record in `people.display_name`, not only against `faces.person_id`. A photo matches when at least one labeled face on that photo refers to a `people` row whose `display_name` matches any requested person-name term.

### Matching semantics stay simple and documented

Each `person_names` entry should use case-insensitive substring matching via SQL `ILIKE '%term%'`. This is a pragmatic fuzzy baseline that matches the current search implementation style without introducing tokenizer, stemming, or edit-distance infrastructure in this slice.

## Expected Request Contract

Within the current schema, add:

- `filters.person_names: list[str] | null`

Meaning:

- values combine with `ANY` semantics within the field
- `person_names` combines with all other filter families using `AND`
- unlabeled faces do not satisfy this filter

Example:

```json
{
  "filters": {
    "person_names": ["inez", "grandma"],
    "has_faces": true
  }
}
```

## Repository Behavior

Implementation should stay centralized in `PhotosRepository._apply_filters(...)`.

Recommended query shape:

- autoload the `people` table in `PhotosRepository.__init__`
- when `filters.person_names` is present, add a correlated `EXISTS` subquery
- join `faces` to `people` on `faces.person_id == people.person_id`
- scope the subquery to the current `photos.photo_id`
- match any provided term against `people.display_name` with case-insensitive substring conditions

This keeps hit selection and facet computation consistent because both already reuse `_apply_filters(...)`.

## Response Behavior

No response-contract change is required for this issue. Search hits may continue returning person identifiers in the existing `people` and `faces` fields. Exposing person display names is a separate concern and should not be bundled into person-name filtering.

## Test Strategy

Add coverage for:

- filtering by a single fuzzy person-name term
- filtering by multiple person-name terms with `OR` semantics
- combining `person_names` with another filter family such as `has_faces` or `path_hints`
- ensuring unlabeled faces do not satisfy `person_names`
- ensuring non-matching names correctly exclude photos

Targeted repository-backed tests are sufficient for this issue even if the checked-in seed corpus does not yet contain representative person-labeled data. If seed fixtures are later expanded with labeled people, they can add higher-level scenario coverage without changing the contract defined here.

## Risks And Constraints

- The current repository stores face-level `person_id` values directly on `faces`, so the filter must avoid assuming names are already denormalized there.
- Substring matching is intentionally limited; it should not be described as full fuzzy search beyond documented partial-name matching.
- This issue shares the central filter pipeline with adjacent Phase 3 search work, so tests should be explicit about cross-filter composition.
