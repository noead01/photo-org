# UI Query Persistence Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize shareable URL query state and browser storage usage so filters, pages, and restored view state have clear ownership.

**Architecture:** Use URL query parameters for user-visible, shareable state. Keep session/local storage only for restoration or preference state that is not intended to be copied in links. Prefer `nuqs` for typed query-state parsing after proving it on Suggestions.

**Tech Stack:** React 18, React Router 6, TypeScript, candidate dependency `nuqs`, Vitest.

---

## Files

- Modify: `apps/ui/package.json`
- Modify: `apps/ui/src/main.tsx` or the app root route tree if a `nuqs` adapter is required there
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.tsx`
- Modify: `apps/ui/src/pages/suggestions/suggestionsRouteMemory.ts`
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.test.tsx`
- Later optional modify: `apps/ui/src/pages/LibraryRoutePage.tsx`
- Later optional modify: `apps/ui/src/pages/library/libraryRouteSearchState.ts`
- Later optional modify: `apps/ui/src/pages/library/libraryRouteMemory.ts`

## Current Problem

- Library manually parses/builds URL query state in `apps/ui/src/pages/library/libraryRouteSearchState.ts:139` and manually syncs it in `apps/ui/src/pages/LibraryRoutePage.tsx:307`.
- Suggestions persists filters only in localStorage via `apps/ui/src/pages/suggestions/suggestionsRouteMemory.ts:35`, so filter state is not shareable as a URL.
- Browser storage helpers are bespoke but include useful domain validation that should not be lost blindly.

## Tasks

### Task 1: Decide and Install Query-State Library

- [ ] Use `nuqs` for typed URL query state.
- [ ] Install dependency: `npm --prefix apps/ui install nuqs`.
- [ ] Add the React Router adapter according to current `nuqs` documentation for React Router 6.
- [ ] Run: `npm --prefix apps/ui run build`.
- [ ] Expected: build succeeds with the adapter configured.

### Task 2: Move Suggestions Filters to URL Query State

- [ ] In `SuggestionsRoutePage`, replace initial localStorage-backed filter refs with URL-backed query values:
`minConfidencePercent`, `maxConfidencePercent`, and `excludedPersonIds`.
- [ ] Use defaults matching current behavior: min `0`, max `100`, excluded people `[]`.
- [ ] Keep page reset behavior when filter values change.
- [ ] Serialize excluded person IDs as a repeatable or delimited query value; choose one format and document it in tests.
- [ ] Preserve backend request serialization in `apps/ui/src/pages/suggestions/api.ts`.

### Task 3: Retire Suggestions LocalStorage Filter Ownership

- [ ] Stop writing Suggestions filters to localStorage in `SuggestionsRoutePage`.
- [ ] Keep `suggestionsRouteMemory.ts` only if a non-shareable preference remains.
- [ ] If no preference remains, delete `suggestionsRouteMemory.ts` and update tests/imports.
- [ ] Update tests that seed `window.localStorage` to instead render at a URL containing the equivalent query parameters.

### Task 4: Test Shareable Suggestions Filters

- [ ] Add or update tests in `SuggestionsRoutePage.test.tsx`.
- [ ] Cover initial load from URL query for min/max confidence.
- [ ] Cover initial load from URL query for excluded person IDs.
- [ ] Cover changing filters updates the URL and triggers page `1`.
- [ ] Cover malformed query values fall back to safe defaults.
- [ ] Run: `npm --prefix apps/ui test -- SuggestionsRoutePage.test.tsx`.
- [ ] Expected: all Suggestions tests pass.

### Task 5: Evaluate Library Query Migration Separately

- [ ] Do not rewrite `LibraryRoutePage` query sync in the same PR unless Suggestions migration is complete and stable.
- [ ] Create a follow-up ticket to replace manual URL sync in `LibraryRoutePage` with typed query-state hooks.
- [ ] Preserve `libraryRouteSearchState.ts` pure parser/build tests until the replacement has equivalent test coverage.

## Acceptance Criteria

- Suggestions filters can be shared by copying the URL.
- Suggestions no longer depends on localStorage for core filter state.
- Browser storage remains reserved for restore/preference use cases such as last library URL.
- The first migration is narrow enough that Library route behavior is not changed accidentally.

