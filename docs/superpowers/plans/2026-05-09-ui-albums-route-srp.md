# UI Albums Route SRP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split album CRUD orchestration, saved-filter-to-library navigation, table rendering, and inline detail pagination into focused modules.

**Architecture:** Keep `AlbumsRoutePage` as composition. Move saved-filter parsing to a pure helper, CRUD/detail state into a hook, and table/detail markup into components.

**Tech Stack:** React 18, React Router 6, TypeScript, Vitest, Testing Library.

---

## Files

- Modify: `apps/ui/src/pages/AlbumsRoutePage.tsx`
- Create: `apps/ui/src/pages/albums/albumLibraryQuery.ts`
- Create: `apps/ui/src/pages/albums/albumLibraryQuery.test.ts`
- Create: `apps/ui/src/pages/albums/useAlbumsRouteState.ts`
- Create: `apps/ui/src/pages/albums/AlbumsCreateRow.tsx`
- Create: `apps/ui/src/pages/albums/AlbumsGrid.tsx`
- Create: `apps/ui/src/pages/albums/AlbumDetailInline.tsx`
- Modify: `apps/ui/src/pages/AlbumsRoutePage.test.tsx`

## Current Problem

`AlbumsRoutePage.tsx` combines:

- Saved filter parsing and library URL construction at `apps/ui/src/pages/AlbumsRoutePage.tsx:22`.
- Album list/detail refresh orchestration at `apps/ui/src/pages/AlbumsRoutePage.tsx:166`.
- Create/update/delete/remove-photo handlers at `apps/ui/src/pages/AlbumsRoutePage.tsx:243`.
- Table and detail rendering at `apps/ui/src/pages/AlbumsRoutePage.tsx:351`.

## Tasks

### Task 1: Extract Album Library Query Helper

- [ ] Move `serializeSavedFilter`, `parseSavedFilterDraft`, `asRecord`, `asStringArray`, `asBool`, `asFiniteNumber`, and `buildLibraryQueryForAlbum` into `albumLibraryQuery.ts`.
- [ ] Keep `buildLibraryQueryForAlbum(album)` pure and independent of React.
- [ ] Add tests covering editable albums, saved filter person/date/location/has-faces/path-hint fields, invalid saved filter values, and JSON draft parse errors.
- [ ] Run: `npm --prefix apps/ui test -- albumLibraryQuery.test.ts`.

### Task 2: Extract Albums Route State Hook

- [ ] Create `useAlbumsRouteState.ts`.
- [ ] Move `albums`, `selectedAlbumId`, `detail`, `detailPage`, loading/error, create form state, row drafts, saving/deleting state, and handlers into the hook.
- [ ] Keep `DETAIL_PAGE_SIZE = 24` in the hook or export it from a small constants file.
- [ ] Return named handler functions for create, save row, delete row, select row, hide row, remove photo, and row draft updates.
- [ ] Preserve current `resolveInitialSessionIdentity()?.userId` behavior.

### Task 3: Extract Create Row Component

- [ ] Create `AlbumsCreateRow.tsx`.
- [ ] Move create-row JSX from `AlbumsRoutePage`.
- [ ] Props should include create name/type/filter draft values, `isCreating`, and callbacks.
- [ ] Keep row markup as `<tr>` so table structure does not change.

### Task 4: Extract Grid Component

- [ ] Create `AlbumsGrid.tsx`.
- [ ] Move table shell, headers, row mapping, row edit fields, and row action buttons.
- [ ] Accept `onOpenAlbum`, `onToggleDetail`, `onSave`, `onDelete`, and row draft callbacks.
- [ ] Use `AlbumsCreateRow` for the first row.

### Task 5: Extract Inline Detail Component

- [ ] Create `AlbumDetailInline.tsx`.
- [ ] Move expanded detail row content, thumbnail rendering, remove-photo button, and previous/next pagination.
- [ ] Props should include `detail`, `onRemovePhoto`, and `onSelectPage`.
- [ ] Preserve accessible labels from the current markup.

### Task 6: Compose Route

- [ ] Update `AlbumsRoutePage` to call `useAlbumsRouteState`, `useNavigate`, and render `AlbumsGrid`.
- [ ] Keep only route header, top-level error/loading surfaces, and navigation callback in the page.
- [ ] Run: `npm --prefix apps/ui test -- AlbumsRoutePage.test.tsx`.
- [ ] Run: `npm --prefix apps/ui test`.
- [ ] Run: `npm --prefix apps/ui run build`.

## Acceptance Criteria

- Saved-filter parsing is directly unit tested outside TSX.
- Album CRUD/detail state is isolated in a hook.
- Route component no longer contains table row markup or saved-filter parsing helpers.
- Existing album route behavior and navigation URLs remain unchanged.

