# Journey: JRN-P3-search-route-deep-link

## Business Outcome

Users can open the Search route directly from a URL and land in the correct shell and navigation state.

## Acceptance Criteria

### Scenario 1: Direct deep link to `/search`

- Given the user opens `/search` directly
- When the app loads
- Then Search page content is shown
- And Search is marked as the active primary route

### Scenario 2: Deep link with query state

- Given the user opens `/search?query=lake`
- When the app loads
- Then the URL query is preserved
- And shell route context remains Search

## Out Of Scope

- Search API responses
- Search filter semantics

## Linked UI Stories

- #165

## Linked Playwright Specs

- `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`
- `apps/ui/tests/e2e/technical/navigation-state.spec.ts`
