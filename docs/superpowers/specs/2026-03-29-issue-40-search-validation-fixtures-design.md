# Issue 40 Search Validation Fixtures Design

## Summary

Issue `#40` should define executable search validation fixtures for the checked-in seed corpus rather than expanding the seed corpus itself. The seed corpus remains the base dataset, while this issue adds the assertion layer that records which supported Phase 3 search requests should return which manifest-backed assets.

## Goals

- Define a checked-in search fixture catalog rooted in the existing `seed-corpus/` data.
- Use manifest asset IDs as the expected-result contract for search validation.
- Keep registered storage source concerns in deterministic test setup rather than in fixture data.
- Add automated tests that validate fixture integrity and execute supported scenarios against seed-corpus-backed search data.

## Non-Goals

- Add new seed-corpus photos to satisfy currently unsupported scenarios.
- Finalize the full canonical Phase 3 search DSL beyond the currently implemented request schema.
- Model persistent storage-source identities in the fixture file itself.

## Design Decisions

### Keep the fixture catalog close to the corpus

The fixture catalog should live under `seed-corpus/` beside `manifest.json`, not inside test-only Python modules. This keeps the executable assertions physically close to the curated dataset they depend on and makes corpus changes and fixture changes reviewable together.

### Use manifest asset IDs as the result contract

Expected matches should be recorded using manifest asset IDs instead of filesystem paths. That makes the fixtures resilient to path-shape refactors inside the application while staying aligned with the curated seed-corpus metadata contract.

### Treat registered storage sources as harness setup

The seed corpus does not intrinsically model a registered storage source. Tests should work around that by registering a temporary storage source rooted at the local `seed-corpus/` directory during setup. The harness can then ingest or seed search data, map searchable photo records back to manifest entries through source-relative paths, and compare the resulting manifest asset IDs to fixture expectations.

## Fixture File Shape

Add a new file such as `seed-corpus/search-fixtures.json` containing scenario entries with fields like:

- `scenario_id`: stable fixture identifier
- `description`: human-readable scenario summary
- `phase_scope`: expected scope classification, limited to executable scenarios in this issue
- `request`: search request payload using the current search API schema
- `expected_asset_ids`: manifest asset IDs expected in the result set
- `notes`: optional fixture-specific assumptions

The fixture catalog should only include scenarios the current seed corpus can already validate. Data-blocked scenarios remain in the scenario catalog and should be covered by a separate follow-up issue for corpus expansion.

## Test Strategy

Add two layers of automated verification:

1. A structural test that loads `manifest.json` and `search-fixtures.json` and fails if a fixture references unknown asset IDs or malformed request data.
2. An execution test that registers a temporary source rooted at `seed-corpus/`, prepares searchable records, runs each fixture request through the search stack, maps returned photos back to manifest asset IDs, and asserts the expected result set.

## Error Handling

- Fail fast if fixture entries reference asset IDs absent from `manifest.json`.
- Fail fast if an ingested or seeded search result cannot be mapped back to a manifest asset ID.
- Do not silently skip unsupported scenarios; they should simply not appear in `search-fixtures.json`.

## Follow-Up Boundary

Create a separate issue for seed-corpus additions required to cover scenarios that the current corpus cannot validate, including person-linked, geotagged, multi-person, and unlabeled-face cases identified by the Phase 3 scenario catalog.
