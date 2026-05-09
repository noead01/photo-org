# Albums Route CRUD + Saved Filter Variants Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a top-level Albums route with list/detail CRUD and membership controls, plus dual Add-to-Album modes (`Editable` and `Saved Filter`) aligned with full Library filter persistence.

**Architecture:** Keep a unified `albums` API surface while separating persistence by subtype (`editable_album_items` for direct membership and `saved_filter_album_rules` for dynamic filter-backed albums). Extend search filters with `album_ids` OR semantics so Library and saved-filter album resolution share one filter contract. Replace prompt-based album actions with explicit modal-driven UX.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, React + React Router + Vitest.

---

## File Structure

- API schema/migrations:
  - `packages/db-schema/photoorg_db_schema/schema.py`
  - `packages/db-schema/photoorg_db_schema/__init__.py`
  - `apps/api/alembic/versions/20260508_000001_album_kinds_and_saved_filters.py` (new)
- API routes and types:
  - `apps/api/app/routers/albums.py`
  - `apps/api/app/main.py`
  - `apps/api/app/schemas/search_request.py`
  - `apps/api/app/repositories/photos_repo.py`
- API tests:
  - `apps/api/tests/test_albums_and_exports_api.py`
  - `apps/api/tests/test_search_service.py`
- UI routing and pages:
  - `apps/ui/src/routes/routeDefinitions.ts`
  - `apps/ui/src/app/AppRouter.tsx`
  - `apps/ui/src/pages/AlbumsRoutePage.tsx` (new)
- UI albums API/state helpers:
  - `apps/ui/src/pages/library/libraryRouteApi.ts`
  - `apps/ui/src/pages/library/libraryRouteTypes.ts`
  - `apps/ui/src/pages/library/libraryRouteSearchState.ts`
  - `apps/ui/src/pages/library/LibrarySearchForm.tsx`
  - `apps/ui/src/pages/library/LibraryActiveFilterChips.tsx`
- UI add-to-album modal:
  - `apps/ui/src/pages/LibraryRoutePage.tsx`
- UI tests:
  - `apps/ui/src/pages/AlbumsRoutePage.test.tsx` (new)
  - `apps/ui/src/pages/LibraryRoutePage.test.tsx`
  - `apps/ui/src/routes/routeDefinitions.test.ts`
  - `apps/ui/src/app/AppShell.test.tsx`
  - `apps/ui/src/pages/library/libraryRouteSearchState.test.ts`

### Task 1: Backend data model for editable/saved-filter split

**Files:**
- Create: `apps/api/alembic/versions/20260508_000001_album_kinds_and_saved_filters.py`
- Modify: `packages/db-schema/photoorg_db_schema/schema.py`
- Modify: `packages/db-schema/photoorg_db_schema/__init__.py`
- Modify: `apps/api/app/storage.py`
- Test: `apps/api/tests/test_albums_and_exports_api.py`

- [ ] **Step 1: Write failing migration/schema tests**

```python
# in test_migration_creates_album_tables (or new tests)
assert "kind" in album_columns
assert inspector.get_columns("saved_filter_album_rules")
assert inspector.get_columns("editable_album_items")
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run --group test python -m pytest apps/api/tests/test_albums_and_exports_api.py::test_migration_creates_album_tables -q`
Expected: FAIL for missing `kind` and split tables.

- [ ] **Step 3: Implement migration + schema updates**

```python
# migration essentials
batch_op.add_column(sa.Column("kind", sa.String(), nullable=False, server_default=sa.text("'editable'")))
op.rename_table("album_items", "editable_album_items")
op.create_table("saved_filter_album_rules", ...)
op.create_index("uq_saved_filter_album_rules_album_id", "saved_filter_album_rules", ["album_id"], unique=True)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run --group test python -m pytest apps/api/tests/test_albums_and_exports_api.py::test_migration_creates_album_tables -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/alembic/versions/20260508_000001_album_kinds_and_saved_filters.py \
  packages/db-schema/photoorg_db_schema/schema.py \
  packages/db-schema/photoorg_db_schema/__init__.py \
  apps/api/app/storage.py \
  apps/api/tests/test_albums_and_exports_api.py
git commit -m "feat(api): split editable and saved-filter album persistence"
```

### Task 2: Albums API CRUD + membership + saved-filter validation

**Files:**
- Modify: `apps/api/app/routers/albums.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_albums_and_exports_api.py`

- [ ] **Step 1: Write failing API tests for CRUD + kind behavior**

```python
create_response = client.post("/api/v1/albums", json={
    "name": "Faces Needing Labels",
    "kind": "saved_filter",
    "filter_json": {"person_names": ["Inez"]}
})
assert create_response.status_code == 201

conflict = client.post("/api/v1/albums", json={"name": "Weekend", "kind": "editable"})
assert conflict.status_code == 409

remove = client.delete(f"/api/v1/albums/{editable_id}/items/photo-1")
assert remove.status_code == 204
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run --group test python -m pytest apps/api/tests/test_albums_and_exports_api.py -q`
Expected: FAIL for missing endpoints/validation.

- [ ] **Step 3: Implement route behavior**

```python
class AlbumKind(str, Enum):
    EDITABLE = "editable"
    SAVED_FILTER = "saved_filter"

# create: enforce unique name per owner (case-insensitive in query)
# saved_filter requires filter_json
# editable add/remove only for editable kind
# list/detail include kind + item_count/resolved_count
# patch supports rename (+ filter_json only for saved_filter)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run --group test python -m pytest apps/api/tests/test_albums_and_exports_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/routers/albums.py apps/api/app/main.py apps/api/tests/test_albums_and_exports_api.py
git commit -m "feat(api): add albums CRUD with editable and saved-filter variants"
```

### Task 3: Search filter support for album_ids OR semantics

**Files:**
- Modify: `apps/api/app/schemas/search_request.py`
- Modify: `apps/api/app/repositories/photos_repo.py`
- Modify: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write failing repository/service tests**

```python
filters = SearchFilters(album_ids=["album-a", "album-b"])
# assert photos in either album are returned
# assert combined with person_names still AND-composes at top-level
```

- [ ] **Step 2: Run targeted tests to verify failure**

Run: `uv run --group test python -m pytest apps/api/tests/test_search_service.py -k album_ids -q`
Expected: FAIL for unknown filter field/no clause.

- [ ] **Step 3: Implement minimal search filter support**

```python
class SearchFilters(BaseModel):
    album_ids: Optional[List[str]] = None

# in repository query builder:
if filters.album_ids:
    where_conditions.append(
        select(self.editable_album_items.c.photo_id)
        .where(self.editable_album_items.c.photo_id == self.photos.c.photo_id)
        .where(self.editable_album_items.c.album_id.in_(filters.album_ids))
        .exists()
    )
```

- [ ] **Step 4: Run targeted tests**

Run: `uv run --group test python -m pytest apps/api/tests/test_search_service.py -k "album_ids or person_names" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/schemas/search_request.py apps/api/app/repositories/photos_repo.py apps/api/tests/test_search_service.py
git commit -m "feat(search): support album_ids filter with OR semantics"
```

### Task 4: Albums route UI (list/detail + CRUD + remove)

**Files:**
- Create: `apps/ui/src/pages/AlbumsRoutePage.tsx`
- Create: `apps/ui/src/pages/AlbumsRoutePage.test.tsx`
- Modify: `apps/ui/src/app/AppRouter.tsx`
- Modify: `apps/ui/src/routes/routeDefinitions.ts`
- Modify: `apps/ui/src/routes/routeDefinitions.test.ts`
- Modify: `apps/ui/src/app/AppShell.test.tsx`
- Modify: `apps/ui/src/pages/library/libraryRouteApi.ts`

- [ ] **Step 1: Write failing UI tests for route and CRUD interactions**

```tsx
expect(screen.getByRole("link", { name: "Albums" })).toBeInTheDocument();
await user.click(screen.getByRole("button", { name: "Create album" }));
expect(await screen.findByText("Weekend Favorites")).toBeInTheDocument();
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm --prefix apps/ui test -- AlbumsRoutePage.test.tsx routeDefinitions.test.ts AppShell.test.tsx`
Expected: FAIL for missing route/page/components.

- [ ] **Step 3: Implement minimal Albums route**

```tsx
// AlbumsRoutePage
// load albums, select album, render items
// create/rename/delete controls
// remove photo button for editable only
```

- [ ] **Step 4: Run tests to verify pass**

Run: `npm --prefix apps/ui test -- AlbumsRoutePage.test.tsx routeDefinitions.test.ts AppShell.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/ui/src/pages/AlbumsRoutePage.tsx apps/ui/src/pages/AlbumsRoutePage.test.tsx \
  apps/ui/src/app/AppRouter.tsx apps/ui/src/routes/routeDefinitions.ts \
  apps/ui/src/routes/routeDefinitions.test.ts apps/ui/src/app/AppShell.test.tsx \
  apps/ui/src/pages/library/libraryRouteApi.ts
git commit -m "feat(ui): add albums route with CRUD and membership detail"
```

### Task 5: Replace Add-to-Album prompt with modal + type radio + info icon

**Files:**
- Modify: `apps/ui/src/pages/LibraryRoutePage.tsx`
- Modify: `apps/ui/src/pages/LibraryRoutePage.test.tsx`
- Modify: `apps/ui/src/pages/library/libraryRouteApi.ts`

- [ ] **Step 1: Write failing tests for modal flow**

```tsx
await user.click(screen.getByRole("button", { name: "Add to album" }));
expect(screen.getByRole("radio", { name: "Editable" })).toBeChecked();
expect(screen.getByRole("radio", { name: "Saved Filter" })).toBeInTheDocument();
expect(screen.getByRole("button", { name: "Album type info" })).toBeInTheDocument();
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm --prefix apps/ui test -- LibraryRoutePage.test.tsx`
Expected: FAIL (no modal/radios/info flow).

- [ ] **Step 3: Implement modal flow**

```tsx
// state: isAlbumModalOpen, albumType, albumName, selectedEditableAlbumId
// saved_filter mode: create-new only with current filters as filter_json
// editable mode: choose existing editable album or create new then add uniquely
// show 409 conflict message inline if album name exists
```

- [ ] **Step 4: Run tests to verify pass**

Run: `npm --prefix apps/ui test -- LibraryRoutePage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/ui/src/pages/LibraryRoutePage.tsx apps/ui/src/pages/LibraryRoutePage.test.tsx apps/ui/src/pages/library/libraryRouteApi.ts
git commit -m "feat(ui): add modal-based add-to-album flow with editable/saved-filter types"
```

### Task 6: Library album facet filter (multi-select OR)

**Files:**
- Modify: `apps/ui/src/pages/library/libraryRouteTypes.ts`
- Modify: `apps/ui/src/pages/library/libraryRouteSearchState.ts`
- Modify: `apps/ui/src/pages/library/libraryRouteSearchState.test.ts`
- Modify: `apps/ui/src/pages/library/LibrarySearchForm.tsx`
- Modify: `apps/ui/src/pages/library/LibraryActiveFilterChips.tsx`
- Modify: `apps/ui/src/pages/LibraryRoutePage.tsx`

- [ ] **Step 1: Write failing tests for URL/filter serialization**

```ts
expect(buildSearchFilters("", "", [], "human_only", "0.8", null, null, [], ["album-1"]))
  .toEqual({ album_ids: ["album-1"] });
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm --prefix apps/ui test -- libraryRouteSearchState.test.ts LibraryRoutePage.test.tsx`
Expected: FAIL for missing `album_ids` support.

- [ ] **Step 3: Implement album facet wiring**

```ts
// URL params: album=<id> (repeatable)
// search filters: album_ids: string[]
// chips + toggles in form with multi-select OR semantics
```

- [ ] **Step 4: Run tests to verify pass**

Run: `npm --prefix apps/ui test -- libraryRouteSearchState.test.ts LibraryRoutePage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/ui/src/pages/library/libraryRouteTypes.ts \
  apps/ui/src/pages/library/libraryRouteSearchState.ts \
  apps/ui/src/pages/library/libraryRouteSearchState.test.ts \
  apps/ui/src/pages/library/LibrarySearchForm.tsx \
  apps/ui/src/pages/library/LibraryActiveFilterChips.tsx \
  apps/ui/src/pages/LibraryRoutePage.tsx
git commit -m "feat(ui): add album facet filtering with multi-select OR semantics"
```

### Task 7: End-to-end verification sweep

**Files:**
- Test-only verification across touched areas.

- [ ] **Step 1: Run API test suite slice**

Run: `uv run --group test python -m pytest apps/api/tests/test_albums_and_exports_api.py apps/api/tests/test_search_service.py apps/api/tests/test_main.py -q`
Expected: PASS.

- [ ] **Step 2: Run UI test suite slice**

Run: `npm --prefix apps/ui test -- AlbumsRoutePage.test.tsx LibraryRoutePage.test.tsx routeDefinitions.test.ts AppShell.test.tsx libraryRouteSearchState.test.ts`
Expected: PASS.

- [ ] **Step 3: Run lint/smoke checks if needed**

Run: `npm --prefix apps/ui run build`
Expected: successful compile.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(albums): add albums route CRUD, saved-filter albums, and library album facet"
```
