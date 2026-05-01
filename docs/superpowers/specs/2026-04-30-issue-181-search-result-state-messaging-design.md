# Issue #181 Search Result State Messaging Design

## Summary

Issue `#181` implements explicit, deterministic messaging patterns for search result states on `/search`:

- empty results for baseline searches
- no-match results for active query/filter searches
- hard-error result states with deterministic retry behavior

The scope is strictly UI-side behavior on top of existing `/api/v1/search` contracts.

## Goals

- Visually and semantically distinguish empty, no-match, loading, and hard-error states.
- Ensure retry always replays the exact last failed request payload.
- Preserve active query/filter context while messaging changes.

## Non-Goals

- backend exception taxonomy changes
- operator diagnostics or failure dashboards
- broad route-state architecture refactors outside search-result messaging

## Current State

`SearchRoutePage` currently renders:

- loading panel while requests are pending
- one generic zero-result message for all successful empty responses
- blocking error panel with Retry button

Gaps relative to `#181`:

- zero-result messaging does not distinguish baseline empty catalog vs active-filter no-match
- retry currently reuses live form state instead of a frozen request snapshot
- message semantics are not framed as explicit result-state patterns

## Design

### 1) Explicit search result state classification

Keep state orchestration in `SearchRoutePage`, but compute a derived result-state classification after each request cycle:

- `loading`: request in flight
- `error`: last request failed
- `empty`: last successful request returned `0` hits and request had no active query/filters
- `no_match`: last successful request returned `0` hits and request had active query and/or filters
- `results`: last successful request returned one or more hits

This is a UI-level derived state; no backend payload changes are required.

### 2) Deterministic retry snapshot

Capture a request snapshot before each search execution:

- `chips`/serialized query
- date/person/location/has-faces/path-hint filters
- sort direction
- page and `cursorByPage`

If request fails, Retry replays that exact snapshot. It does not pull potentially edited draft values from current input controls.

### 3) Messaging behavior

Result-state panels should behave as:

- `loading`: existing loading panel copy remains.
- `error`: existing blocking panel remains with `Retry`; body text remains mapped to the thrown request error.
- `empty`: render explicit baseline-empty message (for no active query/filter state).
- `no_match`: render explicit no-match message for active query/filter state.
- `results`: render result list, no empty/no-match panel.

No extra recovery action is added to `no_match`; panel remains informational only.

### 4) Context preservation

Query chips, typed filters, and URL-synced state remain intact across:

- loading -> error
- error -> retry -> success
- no-match/empty transitions

Only data results and view messaging change; active filter context is not dropped.

## Files

- Modify: `apps/ui/src/pages/SearchRoutePage.tsx`
  - add derived result-state logic
  - add retry snapshot capture/replay
  - split zero-result messaging into empty vs no-match panels
- Modify: `apps/ui/src/pages/SearchRoutePage.test.tsx`
  - add/adjust tests for empty vs no-match messaging distinction
  - add retry snapshot regression test (replay exact failed payload)
  - verify filter/query context remains visible across state transitions

## Test Strategy

Targeted route tests in `SearchRoutePage.test.tsx`:

- empty state when submitting baseline search (no active query/filters) with zero hits
- no-match state when active query/filters yield zero hits
- error state retry replays exact failed payload even if draft inputs changed after failure
- loading/error/no-match states remain visually distinct
- active chips/filters remain rendered through error and retry transitions

## Risks and Mitigations

- Risk: Retry replay could accidentally use stale closures or mutable references.
  - Mitigation: store immutable snapshot object for last attempted request.
- Risk: Empty/no-match classification might drift if “active filter” logic is duplicated.
  - Mitigation: reuse existing active-filter booleans already used for chip rendering.

## Acceptance Criteria Mapping

- no-match visually distinct from loading and hard-error:
  - delivered via explicit `no_match` panel and independent loading/error rendering.
- error provides deterministic retry/recovery:
  - delivered via exact failed-request snapshot replay on Retry.
- state messaging does not drop active filter context:
  - delivered by preserving chips/filter state and URL sync through transitions.
