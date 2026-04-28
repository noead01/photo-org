# Journey: JRN-P2-not-found-recovery

## Business Outcome

Users can recover from an unknown URL without losing orientation or global navigation.

## Acceptance Criteria

### Scenario 1: Unknown path shows recoverable not-found state

- Given the user opens an unknown route
- When the page renders
- Then the heading "Page Not Found" is shown in content
- And primary navigation remains visible

### Scenario 2: Recovery to Browse from not-found page

- Given the user is on a not-found page
- When the user selects `Browse` in primary navigation
- Then the app navigates to `/browse`
- And Browse page content is visible

## Out Of Scope

- Customized 404 branding
- Logging/telemetry for invalid URLs

## Linked UI Stories

- #164

## Linked Playwright Specs

- `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`
