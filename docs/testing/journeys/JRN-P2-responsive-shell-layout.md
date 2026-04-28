# Journey: JRN-P2-responsive-shell-layout

## Business Outcome

Users can keep navigating and inspecting content as viewport width changes between desktop, tablet, and mobile ranges.

## Acceptance Criteria

### Scenario 1: Responsive shell stays usable across target breakpoints

- Given the user opens a primary route (`/search`)
- When the viewport changes to desktop, tablet, and mobile widths
- Then header, primary navigation, and content regions remain visible
- And primary navigation controls remain reachable

### Scenario 2: Route context remains stable while viewport changes

- Given the user is on `/search`
- When the viewport changes between desktop, tablet, and mobile widths
- Then the URL remains `/search`
- And shell route context remains Search

### Scenario 3: Route state survives post-resize navigation

- Given the user has resized to mobile width
- When the user navigates to `/operations`
- Then Operations remains active after additional viewport changes

## Out Of Scope

- Detailed visual polish and spacing parity between breakpoints
- API-backed page content behavior

## Linked UI Stories

- #167

## Linked Playwright Specs

- `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`
