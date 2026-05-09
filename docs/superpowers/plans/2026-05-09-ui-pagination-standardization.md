# UI Pagination Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove duplicated `react-paginate` configuration from Library and Suggestions by introducing one shared pagination wrapper.

**Architecture:** Keep `react-paginate` as the battle-tested OSS component. Create an app-owned wrapper that centralizes labels, class names, clamping, disabled previous/next behavior, and one-based page callbacks.

**Tech Stack:** React 18, TypeScript, `react-paginate`, Testing Library, Vitest.

---

## Files

- Create: `apps/ui/src/pages/shared/BrowsePagination.tsx`
- Create: `apps/ui/src/pages/shared/BrowsePagination.test.tsx`
- Modify: `apps/ui/src/pages/library/LibraryPageNavigator.tsx`
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.tsx`
- Modify: `apps/ui/src/pages/library/LibraryPageNavigator.test.tsx`
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.test.tsx` only if assertions depend on paginator markup

## Current Problem

- `LibraryPageNavigator` configures `ReactPaginate` at `apps/ui/src/pages/library/LibraryPageNavigator.tsx:48`.
- `SuggestionsRoutePage` repeats nearly the same config at `apps/ui/src/pages/SuggestionsRoutePage.tsx:270`.
- Future accessibility or styling changes must be applied in two places.

## Tasks

### Task 1: Add Shared Pagination Wrapper

- [ ] Create `apps/ui/src/pages/shared/BrowsePagination.tsx`.
- [ ] Export `BrowsePaginationProps` with `currentPage`, `pageCount`, `canGoPrevious`, `canGoNext`, `ariaLabel`, and `onPageChange`.
- [ ] Implement clamping internally so callers pass raw page values.
- [ ] Preserve current class names:
`browse-pagination-pages`, `browse-pagination-page-item`, `browse-pagination-page-link`, `browse-pagination-arrow`, `is-active`, `is-disabled`, `browse-pagination-break-item`, `browse-pagination-ellipsis`.
- [ ] Preserve labels:
Previous label `<`, next label `>`, break label `...`, page label `[n]`, aria label `Page n`.
- [ ] Preserve cancellation behavior for disabled previous/next clicks.

### Task 2: Test Wrapper Behavior

- [ ] Add tests in `apps/ui/src/pages/shared/BrowsePagination.test.tsx`.
- [ ] Cover current page rendering, previous/next callback conversion to one-based pages, disabled previous/next suppression, and out-of-range current page clamping.
- [ ] Run: `npm --prefix apps/ui test -- BrowsePagination.test.tsx`.
- [ ] Expected: all new tests pass.

### Task 3: Replace Library Usage

- [ ] Modify `LibraryPageNavigator` to keep the page-size selector and render `BrowsePagination`.
- [ ] Remove direct `ReactPaginate` import from `LibraryPageNavigator`.
- [ ] Keep `LibraryPageNavigator` public props unchanged to avoid broad call-site churn.
- [ ] Run: `npm --prefix apps/ui test -- LibraryPageNavigator.test.tsx`.
- [ ] Expected: existing pagination tests pass with no semantic changes.

### Task 4: Replace Suggestions Usage

- [ ] Modify `SuggestionsRoutePage` to import and render `BrowsePagination`.
- [ ] Remove direct `ReactPaginate` import from `SuggestionsRoutePage`.
- [ ] Pass `ariaLabel="Suggestion pagination"`.
- [ ] Keep `setPage(selected + 1)` behavior by using wrapper `onPageChange={(page) => setPage(page)}`.
- [ ] Run: `npm --prefix apps/ui test -- SuggestionsRoutePage.test.tsx`.
- [ ] Expected: existing suggestion paging/filter tests pass.

### Task 5: Final Verification

- [ ] Run: `npm --prefix apps/ui test`.
- [ ] Run: `npm --prefix apps/ui run build`.
- [ ] Confirm `rg -n "ReactPaginate" apps/ui/src` only reports the shared wrapper.

## Acceptance Criteria

- `ReactPaginate` is imported in exactly one production TSX file.
- Library and Suggestions render identical pagination behavior.
- Existing page-size behavior in Library is unchanged.
- Pagination tests cover the shared wrapper directly.

