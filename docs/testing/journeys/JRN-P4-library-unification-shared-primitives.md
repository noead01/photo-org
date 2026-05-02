# Journey: JRN-P4-library-unification-shared-primitives

## Business Outcome

Browse and Search share deterministic request lifecycle handling and result identity rendering as Library unification progresses.

## Acceptance Criteria

### Scenario 1: Browse uses shared loading/error/retry lifecycle

- Given the user opens `/browse`
- When a request is pending
- Then Browse shows the route loading state
- And a failed follow-up request shows retryable route error feedback
- And selecting Retry restores ready results

### Scenario 2: Browse resets invalid page state deterministically

- Given the user opens `/browse?page=3` without a valid cursor boundary
- When Browse resolves pagination state
- Then the route resets to page 1 and shows the invalid-page messaging

### Scenario 3: Search uses shared loading/error/retry lifecycle and result identity

- Given the user opens `/search` and submits a query
- When a request is pending
- Then Search shows the route loading state
- And results render shared identity primitives (photo heading + path)
- And a failed follow-up request shows retryable route error feedback
- And selecting Retry restores ready results

## Out Of Scope

- Backend search semantics and ranking behavior
- Filter contract redesign

## Linked UI Stories

- [#220](https://github.com/noead01/photo-org/issues/220)

## Linked Playwright Specs

- [apps/ui/tests/e2e/journeys/library-unification-journeys.spec.ts](../../../apps/ui/tests/e2e/journeys/library-unification-journeys.spec.ts)
