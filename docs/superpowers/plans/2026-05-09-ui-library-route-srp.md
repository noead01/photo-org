# UI Library Route SRP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `LibraryRoutePage.tsx` from a multi-responsibility page object into a route orchestrator composed from focused hooks and components.

**Architecture:** Extract state synchronization, result loading, bulk action orchestration, focus restoration, and add-to-album modal rendering. Keep existing child components and pure helpers where they already work.

**Tech Stack:** React 18, React Router 6, TypeScript, Vitest, Testing Library.

---

## Files

- Modify: `apps/ui/src/pages/LibraryRoutePage.tsx`
- Create: `apps/ui/src/pages/library/useLibraryResults.ts`
- Create: `apps/ui/src/pages/library/useLibraryUrlSync.ts`
- Create: `apps/ui/src/pages/library/useLibraryRouteStateSync.ts`
- Create: `apps/ui/src/pages/library/useLibraryBulkActions.ts`
- Create: `apps/ui/src/pages/library/useLibraryReturnFocus.ts`
- Create: `apps/ui/src/pages/library/AddToAlbumDialog.tsx`
- Create tests next to each new hook/component where behavior is not already covered by route tests
- Modify: `apps/ui/src/pages/LibraryRoutePage.test.tsx`

## Current Problem

`LibraryRoutePage.tsx` owns too many independent reasons to change:

- URL parse/apply/sync at `apps/ui/src/pages/LibraryRoutePage.tsx:90`, `:307`, and `:353`.
- Result loading and facet count state at `apps/ui/src/pages/LibraryRoutePage.tsx:461`.
- Browser focus restoration at `apps/ui/src/pages/LibraryRoutePage.tsx:546`.
- Bulk selection expansion and export/download behavior at `apps/ui/src/pages/LibraryRoutePage.tsx:615`.
- Add-to-album modal state and JSX at `apps/ui/src/pages/LibraryRoutePage.tsx:690` and `:1137`.

## Tasks

### Task 1: Extract Result Loading Hook

- [ ] Create `useLibraryResults.ts`.
- [ ] Move `photos`, `totalCount`, facet counts, loading/error request lifecycle, and `fetchLibraryPage` effect into the hook.
- [ ] Accept a single parameter object representing the current search/page state.
- [ ] Return `photos`, `totalCount`, `facetHasFacesCounts`, `facetPathHintCounts`, `isLoading`, `error`, `requestRetry`, and `feedbackViewState`.
- [ ] Keep `useRouteRequestState` usage inside the hook.
- [ ] Run: `npm --prefix apps/ui test -- LibraryRoutePage.test.tsx`.

### Task 2: Extract URL Sync Hook

- [ ] Create `useLibraryUrlSync.ts`.
- [ ] Move parsed URL state signature, suppress/applying refs, URL-to-state application, and state-to-URL navigation logic out of the page.
- [ ] Keep `parseLibraryUrlState` and `buildLibraryUrlQuery` as pure helpers.
- [ ] Return the initial parsed state and a callback/adapter that route state setters can use.
- [ ] Preserve current `replace: true` navigation behavior.
- [ ] Run: `npm --prefix apps/ui test -- LibraryRoutePage.test.tsx`.

### Task 3: Extract Route State Sync Hook

- [ ] Create `useLibraryRouteStateSync.ts`.
- [ ] Move library selection/view route state serialization and `navigate(..., { state })` synchronization out of the page.
- [ ] Move equality helpers from the bottom of `LibraryRoutePage.tsx` into this hook or a colocated pure helper file.
- [ ] Add pure helper tests for equality functions if they are exported.

### Task 4: Extract Return Focus Hook

- [ ] Create `useLibraryReturnFocus.ts`.
- [ ] Move pending return focus ref and `document.querySelector`/`window.setTimeout` effect out of `LibraryRoutePage`.
- [ ] Accept `headingRef`, `isLoading`, `error`, and `photos`.
- [ ] Preserve current fallback to heading focus.
- [ ] Keep direct DOM access isolated in this hook.

### Task 5: Extract Bulk Actions Hook

- [ ] Create `useLibraryBulkActions.ts`.
- [ ] Move `resolveActiveScopePhotoIds`, `downloadBlob`, `handleExportAction`, notification pushing, and action error handling into the hook.
- [ ] Keep `downloadBlob` in a small browser utility if it will be reused elsewhere.
- [ ] Keep `createAlbum`, `addPhotosToAlbum`, and `exportPhotos` calls in the hook, not the page.
- [ ] Return `notifications`, `dismissNotification`, `handleLibraryAction`, and add-to-album dialog state/actions.

### Task 6: Extract Add To Album Dialog

- [ ] Create `AddToAlbumDialog.tsx`.
- [ ] Move modal JSX from `LibraryRoutePage.tsx:1137`.
- [ ] Props should include `isOpen`, `isSaving`, `photoCount`, `albumKind`, `albumName`, `showAlbumTypeInfo`, `error`, change handlers, `onClose`, and `onSubmit`.
- [ ] Add a component test that covers close, kind toggle, name change, and submit.

### Task 7: Trim LibraryRoutePage

- [ ] Compose the new hooks/components in `LibraryRoutePage`.
- [ ] Keep filter input handlers in the route only until a separate `useLibraryFilters` refactor is planned.
- [ ] Confirm `LibraryRoutePage.tsx` no longer imports `FormEvent`.
- [ ] Confirm `LibraryRoutePage.tsx` no longer directly calls `fetchLibraryPage` except through hooks.
- [ ] Run: `npm --prefix apps/ui test -- LibraryRoutePage.test.tsx`.

### Task 8: Final Verification

- [ ] Run: `npm --prefix apps/ui test`.
- [ ] Run: `npm --prefix apps/ui run build`.
- [ ] Run: `wc -l apps/ui/src/pages/LibraryRoutePage.tsx`.
- [ ] Expected: route file is materially smaller and has fewer independent effect blocks than before.

## Acceptance Criteria

- `LibraryRoutePage` remains responsible for route composition and filter handler wiring, not data fetching, browser downloads, modal markup, or DOM focus restoration.
- Existing Library tests pass without weakening assertions.
- New hooks/components have focused tests where behavior moved out of route tests.

