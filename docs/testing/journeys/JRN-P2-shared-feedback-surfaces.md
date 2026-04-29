# Journey: JRN-P2-shared-feedback-surfaces

## Business Outcome

Users can recover from route feedback states without leaving the current workflow, keeping progress and orientation in place.

## Acceptance Criteria

### Scenario 1: Loading surface communicates route progress

- Given the user opens `/search?demoState=loading`
- When the Search route renders through the shared feedback surface
- Then the route loading status text is visible for the Search workflow

### Scenario 2: Retry recovers from route error into ready state

- Given the user opens `/search?demoState=error`
- When the user selects Retry
- Then the Search ready heading appears
- And a success notification confirms Search is ready

## Out Of Scope

- Network-level retry behavior against backend APIs
- Notification auto-dismiss timing and animation polish

## Linked UI Stories

- [#168](https://github.com/noead01/photo-org/issues/168)

## Linked Playwright Specs

- [apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts](../../../apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts)
