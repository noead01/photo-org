# Issue #231: Unified Library Route And Scope-Aware Action Bar Design

## Summary

Replace separate Browse and Search routes with a single `/library` route that hosts:

- Library search and filter controls
- Library photo result display
- A scope-aware action bar for `Add to album` and `Export`

The action bar must only appear for active selection scope and must enforce deterministic enablement/disabled explanations using real permission and conflicting-job signals.

## Goals

- Remove `/browse` and `/search` as user-facing primary routes.
- Introduce `/library` as the canonical route for browse/search/filter/result workflows.
- Implement a shared, route-agnostic Library action bar primitive.
- Support accessibility requirements for keyboard order, semantics, and disabled reason messaging.
- Preserve deterministic route-local state behavior for selection and return-focus flows.

## Non-Goals

- Implementing album/export backend business actions.
- Redesigning global feedback surface primitives.
- Building speculative multi-route compatibility layers after `/library` cutover.

## Architecture

### Route Structure

- Remove `browse` and `search` entries from `PRIMARY_ROUTE_DEFINITIONS`.
- Add `library` route definition with path `/library`.
- Route tree renders a new `LibraryRoutePage` at `/library`.
- Remove `/browse` and `/search` routes instead of redirecting.

### Page Composition

Create `LibraryRoutePage` as the single composition surface:

- Query/filter control section (currently in Search route behavior).
- Selection scope section (existing selection model primitives).
- Action bar section (new `LibraryActionBar` component).
- Results section (current browse-style visual library cards).
- Existing route-local feedback surface handling for loading/error/notifications.

### Shared Library Primitives

Use or extend `apps/ui/src/pages/library/*` modules so behavior is route-agnostic:

- Selection state and count logic (`librarySelection.ts`).
- Pagination and request lifecycle primitives.
- URL serialization/parsing helpers for library query state.
- New action bar component and enablement resolver helpers.

## Action Bar UX And Behavior

### Actions In Scope

- `Add to album`
- `Export`

### Visibility Rule

The action bar is visible only when effective selection scope count is greater than zero.

Selection count is computed from active scope:

- `selected`: explicit selected IDs count
- `page`: current page result count
- `allFiltered`: total filtered count

### Real Enablement Signals

#### 1. Selection Scope

- Source: existing library selection reducer + count resolver.
- Requirement: count must be > 0 for either action to be enabled.

#### 2. Permission Capability

- Extend session bootstrap identity to include capabilities.
- Proposed shape:
  - `window.__PHOTO_ORG_SESSION__.capabilities.addToAlbum: boolean`
  - `window.__PHOTO_ORG_SESSION__.capabilities.export: boolean`
- Parse and validate capability fields alongside existing session identity bootstrap logic.
- If session/capabilities missing or invalid, capability defaults to `false` for safety.

#### 3. Conflicting Job Signal

- Poll `GET /api/v1/operations/activity`.
- Treat conflict as active when:
  - `ingest_queue.summary.processing_count > 0`
- Conflict state disables both action buttons.

### Deterministic Enablement Matrix

For each action button, enabled when all are true:

1. Selection count > 0
2. Capability for that action is true
3. No conflicting job

Disabled reason precedence (first matching reason shown):

1. `No selection scope active.`
2. `You do not have permission for this action.`
3. `Action temporarily unavailable while ingest processing is active.`

Each disabled action renders a visible reason string in the action bar and binds it with `aria-describedby`.

## Accessibility

- Action bar container uses semantic grouping with clear label, e.g. `aria-label="Library actions"`.
- Buttons are native `<button>` elements in DOM order.
- Disabled states are native (`disabled`) plus `aria-describedby` to reason text.
- Focus behavior:
  - If action bar appears, do not auto-steal focus.
  - If action bar disappears while focus is inside it, move focus to stable page heading.
- Selection summary and action-state changes should be announced via polite live-region messaging where already used.

## Responsive Behavior

- Desktop: horizontal action bar row with summary and actions.
- Mobile: stacked layout with full-width action buttons and wrapped reason text.
- Maintain usability at existing shell breakpoints (`1024px`, `640px`) in current CSS strategy.

## Route-Local Navigation State

Replace browse-specific return-state keys with library-scoped equivalents.

Current pattern:

- `returnToBrowseSearch`
- `returnFocusPhotoId`
- `browseSelection`

Target pattern:

- `returnToLibrarySearch`
- `returnFocusPhotoId`
- `librarySelection`

Photo detail back-navigation must restore query, selection scope state, and focus target against `/library`.

## Testing Strategy

### Unit Tests

- Action enablement resolver:
  - all-true enables
  - each missing prerequisite disables with correct reason
  - reason precedence deterministic
- Session bootstrap parsing for capability shape validation.

### Component Tests

- Action bar hidden when effective scope count is zero.
- Action bar visible when scope count is positive.
- Disabled reasons rendered and bound through `aria-describedby`.
- Keyboard tab order remains valid when bar appears/disappears.
- Focus fallback to heading when bar unmounts while focused.

### Route/Integration Tests

- `/library` route renders canonical unified surface.
- `/browse` and `/search` are no longer primary routes.
- Photo detail return flow restores library state and focus.
- Operations conflict fetch affects button states deterministically.

## Risks And Mitigations

- Risk: broad route migration regression.
  - Mitigation: isolate route-definition edits first and update route tests immediately.
- Risk: permission bootstrap mismatch.
  - Mitigation: strict schema parsing with safe-default deny behavior and tests.
- Risk: conflict-state fetch churn.
  - Mitigation: use controlled polling cadence and route request lifecycle handling with deterministic fallback.

## Implementation Order

1. Route-definition and route-tree migration to `/library`.
2. `LibraryRoutePage` extraction/composition from existing Browse/Search behavior.
3. Session capability parsing extension.
4. Operations conflict-state integration for action gating.
5. `LibraryActionBar` implementation and wiring.
6. Detail-route return-state key migration.
7. Tests and cleanup of obsolete Browse/Search-only assumptions.

## Acceptance Criteria Mapping

- Action bar appears only with active scope: covered by visibility rule and component tests.
- Deterministic enabled/disabled logic with explanation: covered by matrix and resolver tests.
- Valid focus order when bar appears/disappears: covered by accessibility behavior and tests.
- Mobile and desktop usability: covered by responsive layout rules and component behavior checks.
