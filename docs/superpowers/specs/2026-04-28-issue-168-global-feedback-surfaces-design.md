# Issue 168 Global Feedback Surfaces Design

Date: 2026-04-28
Scope: Shared UI loading, blocking error, and non-blocking notification surfaces for Phase 2 primary routes
Issue: [#168](https://github.com/noead01/photo-org/issues/168)

## Summary

Implement shared feedback surfaces for all current primary placeholder routes (`/browse`, `/search`, `/labeling`, `/suggestions`, `/operations`) so route pages do not re-implement ad hoc loading/error/notification patterns.

This slice adds reusable feedback primitives, wires them into every primary route page, and documents the pattern for future UI stories.

## Goals

- define one shared route-level loading pattern usable across browse/detail workflows
- define one shared blocking error pattern with deterministic recovery action
- define one shared notification pattern for non-blocking success/warning outcomes
- keep shell frame behavior stable while content-level feedback state changes
- add documentation and traceability for feedback behavior as a reusable UI contract

## Non-Goals

- feature-specific business logic for when backend operations trigger feedback
- backend API error schema redesign
- global cross-app state management for all future feedback use cases
- visual redesign of unrelated shell layout/navigation behavior

## Decision Snapshot

- consumer scope: all current primary routes
- route-level loading: inline content loading panel
- blocking route-level error: title + message + `Retry` button
- notifications: auto-dismiss by default with fixed timeout and manual dismiss
- action-level loading: local to control/panel, not full-page
- implementation approach: shared reusable feedback components plus page-level wrapper API

## Visual Companion Artifact

- `.superpowers/brainstorm/2-1777418449/content/scope-consumers-1.html`

## Architecture

Introduce a shared feedback layer in `apps/ui/src/app/feedback/` composed of:

- `RouteLoadingState` for route content loading
- `RouteErrorState` for blocking content errors with retry
- `ToastStack` for non-blocking success/warning notifications
- `FeedbackSurface` as the page-level composer selecting route view state and rendering notifications

All five primary placeholder pages render through `FeedbackSurface` so the behavior stays consistent and testable.

## Components And Contracts

### Route Loading Surface

- displayed when `viewState === "loading"`
- rendered inside main content area to preserve shell/header/nav continuity
- text and semantics are deterministic for testability

### Route Error Surface

- displayed when `viewState === "error"`
- requires structured error payload:
  - `title: string`
  - `message: string`
- requires `onRetry: () => void`
- does not add secondary navigation action in this issue

### Notification Surface

- queue entries shaped as:
  - `id: string`
  - `tone: "success" | "warning"`
  - `message: string`
  - optional `timeoutMs` (defaults to fixed shared timeout)
- each toast supports:
  - deterministic auto-dismiss by timeout
  - deterministic manual dismiss by id
- queue behavior is deterministic FIFO

## State Model

Per route page, shared wrapper state is:

- `viewState: "loading" | "error" | "ready"`
- `error: { title: string; message: string } | null`
- `notifications: NotificationEntry[]`

Behavior rules:

- route-level loading and error are mutually exclusive with ready content
- notifications can coexist with any `viewState`
- action-level loading remains local and does not replace route-level state

## Integration Plan

### UI Code

- add new feedback components in `apps/ui/src/app/feedback/`
- update `PrimaryRoutePage` to consume `FeedbackSurface`
- wire deterministic simulated state coverage across:
  - browse
  - search
  - labeling
  - suggestions
  - operations
- extend `app-shell.css` with shared feedback surface styling and tokens

### Documentation

- add a new journey acceptance-criteria doc for shared feedback behavior
- update `docs/testing/journey-traceability.md` to map journey id -> Playwright spec(s) -> issue `#168`
- keep future stories pointed at these shared patterns rather than route-local reinvention

## Testing Strategy

### Unit/Component Tests

- add focused tests for `RouteLoadingState`
- add focused tests for `RouteErrorState` retry behavior
- add focused tests for `ToastStack`:
  - fixed-time auto-dismiss
  - manual dismiss
  - deterministic queue removal
- add or extend page-level tests to verify shared usage across all primary routes

### E2E Coverage

- ensure smoke journey coverage continues to pass for shell continuity
- add/extend journey coverage for feedback surfaces using deterministic simulated states

## Verification Commands

Run from `apps/ui`:

1. `npm run test`
2. `npm run test:e2e:smoke`

## Risks And Mitigations

- risk: duplicated feedback logic reappears in future routes
  - mitigation: make `FeedbackSurface` the default route-page pattern and document it in journey traceability
- risk: toast timing introduces flaky tests
  - mitigation: use deterministic timeout constants and fake timer control in unit tests
- risk: route state explosion in placeholder pages
  - mitigation: keep route state model minimal (`loading | error | ready`) and push richer logic to future feature stories

## Open Questions

- none for this design slice
