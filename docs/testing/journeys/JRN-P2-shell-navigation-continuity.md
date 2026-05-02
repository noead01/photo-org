# Journey: JRN-P2-shell-navigation-continuity

## Business Outcome

Users can navigate between primary sections without losing the persistent shell frame.

## Acceptance Criteria

### Scenario 1: Library to Labeling keeps shell frame mounted

- Given the user is on `/library`
- When the user selects `Labeling` from primary navigation
- Then the header and primary navigation remain visible
- And the main content updates to the Labeling page title

### Scenario 2: Shell route context updates with navigation

- Given the user is on `/library`
- When the user selects a different primary route
- Then shell route context reflects the selected route

## Out Of Scope

- Search results behavior
- API-backed data loading

## Linked UI Stories

- #164

## Linked Playwright Specs

- `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`
