# Issue #174 Tokenized Search Bar Design

Date: 2026-04-29
Issue: #174
Epic: #160

## Summary

Implement the Phase 3 Search route text-query interaction model with phrase-level query chips. Users can submit text via Enter or a Search button, accumulate multiple phrase chips, clear phrases by dismissing chips, and trigger deterministic search requests against `/api/v1/search`.

## Goals

- deliver tokenized search input interactions for query submit and reset behavior in the `/search` route
- represent active text query state explicitly in UI via chips
- keep behavior deterministic across submit, clear, retry, and empty-input paths
- stay compatible with current backend contract (`q` is a single string)

## Non-Goals

- URL query synchronization and deep-link restoration (tracked by #179)
- date/person/location/facet filter controls (covered by #175-#178)
- search-state architectural refactor shared with browse route (follow-up story)
- backend parser/query semantics redesign

## Architecture

- Add a dedicated route component: `apps/ui/src/pages/SearchRoutePage.tsx`.
- Update `apps/ui/src/app/AppRouter.tsx` so `/search` renders `SearchRoutePage`.
- Keep `PrimaryRoutePage` for remaining placeholder routes (`/labeling`, `/suggestions`, `/operations`).
- Keep implementation story-scoped in one page component; avoid introducing new shared abstractions in #174.

## Interaction Model

### Query submission

- Input accepts free-form text.
- Submission triggers from:
  - keyboard Enter on the input
  - clicking a `Search` button
- On submit:
  - `trim()` input text
  - if empty or whitespace-only, do nothing (no chip mutation, no request)
  - if non-empty, append one chip using the full phrase exactly as entered after trim
  - clear input field
  - execute a search request

### Tokenized chips

- One submitted phrase equals one chip.
- Multiple submits accumulate multiple chips in insertion order.
- Chip list order is stable and deterministic.

### Reset/clear behavior

- No standalone `Clear` button.
- Clearing occurs only by dismissing a chip (`x` action).
- On dismiss:
  - remove selected chip
  - re-run search using remaining chips

## Request Mapping

Backend currently expects one text query field `q: string | null`.

For #174, map chips to backend query by joining phrase chips with single spaces in chip order:

- `q = chips.join(" ")`

Request body baseline for this story:

- `q`: serialized chips
- `sort`: `{ by: "shot_ts", dir: "desc" }`
- `page`: `{ limit: 24, cursor: null }`

When no chips remain after dismissing, `q` becomes empty string and request executes in default unfiltered text mode, preserving deterministic behavior.

## State Model

`SearchRoutePage` local state:

- `draftQuery: string` — current input value
- `queryChips: string[]` — submitted phrase chips in order
- `results` — latest response item list
- `totalCount: number`
- `isLoading: boolean`
- `error: string | null`
- `reloadToken: number` — deterministic retry trigger

Derived values:

- `serializedQuery = queryChips.join(" ")`
- request summary label for polite status updates

## UI Feedback Behavior

### Loading

- Show route-local loading panel with `role="status"` and `aria-live="polite"`.
- Shell and navigation remain mounted.

### Error

- Show route-local retry panel with retry button.
- Retry replays request based on current chips.

### Empty results

- Show explicit no-match panel when request succeeds with zero items.

### Success

- Show result list/grid for returned photos.
- Show concise result summary (`Showing X of Y photos`).
- Show active query chips as visible filter context.

### Empty/invalid input behavior

- Whitespace-only submit is explicit no-op by design.
- Existing chips/results remain unchanged.

## Accessibility Baseline

- Input and Search button are keyboard-operable.
- Chips expose labeled dismiss buttons.
- Loading/error status messaging uses semantic roles and polite live region where applicable.
- Route heading remains level-1 and shell semantics remain unchanged.

## Testing Strategy

Add `apps/ui/src/pages/SearchRoutePage.test.tsx` covering:

- Enter submit appends one phrase chip and issues request
- Search button submit matches Enter behavior
- whitespace-only submit is no-op (no request/chip mutation)
- multiple submits preserve chip order and request serialization order
- dismissing a chip updates chips and re-fetches with recomputed `q`
- loading/error/empty/success states render deterministically

Update existing shell routing tests (`apps/ui/src/app/AppShell.test.tsx`) to reflect `/search` rendering the real search page controls rather than generic placeholder text.

## Follow-Up Story

Create a follow-up implementation story to refactor shared browse/search concerns:

- extract shared request lifecycle and feedback state handling hook(s)
- extract shared photo-result card/list primitives where beneficial
- centralize query/filter serialization helpers ahead of #175-#181

This follow-up is intentionally out of scope for #174.

## Risks And Mitigations

- Risk: accidental scope overlap with #179 URL sync.
  - Mitigation: avoid reading/writing search params for #174 state.
- Risk: behavior drift between Enter and button submit.
  - Mitigation: route both through one submit handler and test both paths.
- Risk: ambiguity around empty query behavior.
  - Mitigation: enforce no-op submit rule and test it directly.

## Acceptance Criteria Mapping (Issue #174)

- Text query submit and clear interactions deterministic:
  - covered by single submit path, chip-dismiss clear path, deterministic state transitions.
- Query state reflected consistently in UI:
  - chips are source of truth and are always visible.
- Invalid/empty query behavior explicit:
  - whitespace-only submit defined and tested as no-op.
