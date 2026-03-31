# Issue 35 Date Range Filtering Design

## Summary

Issue `#35` should turn the existing date filter into an explicit, tested Phase 3 contract over canonical `shot_ts`. The goal is not to redesign the broader search DSL, but to make date filtering predictable: inclusive day-based boundaries, null timestamp exclusion when a date filter is active, and seed-corpus-backed verification of the July 2022 scenario.

## Goals

- Define clear semantics for `filters.date.from` and `filters.date.to`.
- Ensure date filtering operates on canonical `photos.shot_ts`.
- Exclude rows with null `shot_ts` whenever a date filter is present.
- Add seed-corpus-backed verification for the representative July 2022 scenario.

## Non-Goals

- Rename the public request shape away from `date`.
- Add relative-language handling such as "before the birthday weekend".
- Add timezone-localized interpretation beyond the current UTC-based stored timestamps.
- Redesign sorting or pagination behavior.

## Design Decisions

### Preserve the current outward request shape

The current request schema already models:

```json
{
  "filters": {
    "date": {
      "from": "2022-07-01",
      "to": "2022-07-31"
    }
  }
}
```

`#35` should keep that shape for compatibility and tighten its semantics instead of introducing a larger contract change.

### Date bounds are inclusive day boundaries

The expected behavior should be:

- `from` means inclusive start of day at `00:00:00`
- `to` means inclusive end of day at `23:59:59.999...`

This matches the scenario catalog intent for "photos from July 2022" and keeps request values human-readable.

### Null `shot_ts` rows are excluded when date filtering is active

Photos without canonical timestamps cannot satisfy a bounded date query. When either `from` or `to` is present, rows with null `shot_ts` should not appear in results.

### The implementation should avoid ad hoc SQL text fragments

The current repository implementation uses raw SQL text interpolation for date boundaries. `#35` should replace that with typed Python `datetime` values passed through SQLAlchemy expressions so the behavior is safer and easier to reason about across SQLite and PostgreSQL.

## Test Strategy

Add or tighten coverage for:

- `from`-only filtering
- `to`-only filtering
- bounded `from` + `to` filtering
- exclusion of null `shot_ts` rows from date-filtered results
- the existing seed-corpus fixture for July 2022 remaining green

## Seed-Corpus Contract

The current seed corpus already supports the representative July 2022 scenario. `seed-corpus/search-fixtures.json` should continue to carry that scenario as an executable contract rather than requiring new corpus assets.
