# Storage Source Ingest Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the watched-folder plus container-mount ingest contract with centrally managed storage sources, marker-file identity, source-relative watched folders, and centrally durable thumbnails.

**Architecture:** Extend the schema first so source identity, aliases, watched-folder ownership, and thumbnail metadata have durable storage. Then add source registration and source-aware scan orchestration in the API layer, followed by CLI/operator contract changes and doc updates that remove the old container-mount mental model. Preserve the existing conservative unreachable-storage behavior, but move the trust boundary from raw scan paths to validated storage sources.

**Tech Stack:** Python, SQLAlchemy Core, Alembic migrations, pytest, SQLite test DBs, existing API/CLI packages in `apps/api` and `apps/cli`

---

## File Map

**Schema and migrations**

- Modify: `packages/db-schema/photoorg_db_schema/schema.py`
- Modify: `packages/db-schema/photoorg_db_schema/__init__.py`
- Modify: `apps/api/alembic/versions/20260321_000001_initial_schema.py`
- Modify: `apps/api/app/storage.py`
- Test: `apps/api/tests/test_schema_definition.py`
- Test: `apps/api/tests/test_migrations.py`

**New source registration and scan services**

- Create: `apps/api/app/services/storage_sources.py`
- Create: `apps/api/app/services/source_registration.py`
- Create: `apps/api/app/services/thumbnails.py`
- Modify: `apps/api/app/services/file_reconciliation.py`
- Modify: `apps/api/app/processing/ingest.py`
- Modify: `apps/api/app/db/ingest_runs.py`
- Test: `apps/api/tests/test_storage_sources.py`
- Test: `apps/api/tests/test_source_registration.py`
- Test: `apps/api/tests/test_ingest.py`

**API and CLI surface**

- Modify: `apps/api/app/cli.py`
- Modify: `apps/cli/cli/queue_client.py`
- Create: `apps/api/app/routers/storage_sources.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_cli.py`
- Test: `apps/cli/tests/test_main.py`
- Test: `apps/cli/tests/test_queue_client.py`
- Test: `apps/api/tests/test_main.py`

**Docs**

- Modify: `README.md`
- Modify: `ROADMAP.md`
- Modify: `DESIGN.md`

## Task 1: Extend The Schema Around Storage Sources

**Files:**

- Modify: `packages/db-schema/photoorg_db_schema/schema.py`
- Modify: `packages/db-schema/photoorg_db_schema/__init__.py`
- Modify: `apps/api/alembic/versions/20260321_000001_initial_schema.py`
- Modify: `apps/api/app/storage.py`
- Test: `apps/api/tests/test_schema_definition.py`
- Test: `apps/api/tests/test_migrations.py`

- [ ] **Step 1: Write failing schema tests for source-aware tables and columns**

Add assertions covering:

- `storage_sources` table with durable ID, display name, marker metadata, availability state, failure reason, timestamps
- `storage_source_aliases` table keyed to `storage_sources`
- `watched_folders.storage_source_id`
- watched-folder relative-path contract replacing unique `container_mount_path`
- thumbnail metadata storage, either on `photos` or in a dedicated table

- [ ] **Step 2: Run schema tests to verify failure**

Run: `uv run python -m pytest apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py -q`

Expected: FAIL because the new tables and columns do not exist yet.

- [ ] **Step 3: Update canonical schema exports**

Modify `packages/db-schema/photoorg_db_schema/schema.py` and `packages/db-schema/photoorg_db_schema/__init__.py` to add:

- `storage_sources`
- `storage_source_aliases`
- thumbnail persistence table or fields
- updated `watched_folders` contract

Keep names and constraints simple and explicit. Do not keep `container_mount_path` as a required product-facing identity field.

- [ ] **Step 4: Update migration coverage**

Reflect the new schema in `apps/api/alembic/versions/20260321_000001_initial_schema.py`. If the repository expects initial-schema edits instead of additive migrations at this stage, keep the migration authoritative and aligned with the canonical schema tests.

- [ ] **Step 5: Export new tables through the storage module**

Update `apps/api/app/storage.py` so the rest of the app can import the new tables through the existing storage boundary.

- [ ] **Step 6: Run schema tests to verify pass**

Run: `uv run python -m pytest apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py -q`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add packages/db-schema/photoorg_db_schema/schema.py \
  packages/db-schema/photoorg_db_schema/__init__.py \
  apps/api/alembic/versions/20260321_000001_initial_schema.py \
  apps/api/app/storage.py \
  apps/api/tests/test_schema_definition.py \
  apps/api/tests/test_migrations.py
git commit -m "feat(schema): add storage source ingest model"
```

## Task 2: Add Storage Source Registration And Marker Validation

**Files:**

- Create: `apps/api/app/services/storage_sources.py`
- Create: `apps/api/app/services/source_registration.py`
- Modify: `apps/api/app/services/file_reconciliation.py`
- Test: `apps/api/tests/test_storage_sources.py`
- Test: `apps/api/tests/test_source_registration.py`

- [ ] **Step 1: Write failing tests for registration and marker-driven identity**

Cover:

- registering a new share creates a `storage_source`
- registration writes or records marker-file metadata
- re-registering the same share through a different alias resolves to the existing source
- missing or conflicting marker paths produce explicit failures instead of duplicate source creation

Use temp directories to simulate reachable roots and marker files. Keep tests at the service layer first.

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `uv run python -m pytest apps/api/tests/test_source_registration.py apps/api/tests/test_storage_sources.py -q`

Expected: FAIL because the new services do not exist.

- [ ] **Step 3: Implement source repository helpers**

In `apps/api/app/services/storage_sources.py`, add focused helpers for:

- creating and loading `storage_source` rows
- attaching aliases
- updating source availability state
- looking up an existing source by marker identity

Keep this file DB-oriented and avoid filesystem side effects here.

- [ ] **Step 4: Implement registration orchestration**

In `apps/api/app/services/source_registration.py`, implement:

- share root validation
- marker-file read/write helpers
- source creation flow
- existing-source resolution via marker

Keep marker serialization minimal and versioned.

- [ ] **Step 5: Run the focused tests to verify pass**

Run: `uv run python -m pytest apps/api/tests/test_source_registration.py apps/api/tests/test_storage_sources.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/storage_sources.py \
  apps/api/app/services/source_registration.py \
  apps/api/tests/test_storage_sources.py \
  apps/api/tests/test_source_registration.py
git commit -m "feat(api): add storage source registration services"
```

## Task 3: Make Ingest And Reconciliation Source-Aware

**Files:**

- Modify: `apps/api/app/processing/ingest.py`
- Modify: `apps/api/app/services/file_reconciliation.py`
- Modify: `apps/api/app/db/ingest_runs.py`
- Test: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write failing ingest tests for source-aware scanning**

Add coverage for:

- ingest operates on a registered source and watched-folder relative path
- a reachable source ingests new files and reconciles missing files normally
- an unreachable source updates source availability but does not advance missing/deleted lifecycle
- marker mismatch aborts the scan before deletion inference

Reuse existing unreachable-storage test patterns where possible rather than introducing a second lifecycle style.

- [ ] **Step 2: Run ingest tests to verify failure**

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -q`

Expected: FAIL because ingest still depends on raw roots and `container_mount_path`.

- [ ] **Step 3: Refactor watched-folder helpers around source identity**

Update `apps/api/app/services/file_reconciliation.py` so watched folders are ensured by `storage_source_id + relative_path`, not by raw scan path plus container mount path.

Preserve:

- active/unreachable state transitions
- conservative missing/deleted handling

Move availability state to the source level as the primary status, and keep folder-level status only if tests show it is still useful.

- [ ] **Step 4: Refactor ingest orchestration**

Update `apps/api/app/processing/ingest.py` so the central flow:

- resolves a source alias
- validates the marker
- scans watched-folder relative roots under the source
- builds canonical photo identity from source-relative paths
- records source-aware run failures

Remove user-facing reliance on `container_mount_path` from the main ingest path.

- [ ] **Step 5: Align ingest-run persistence**

Update `apps/api/app/db/ingest_runs.py` so runs can be associated with the right source and watched folder after the schema shift.

- [ ] **Step 6: Run ingest tests to verify pass**

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -q`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/processing/ingest.py \
  apps/api/app/services/file_reconciliation.py \
  apps/api/app/db/ingest_runs.py \
  apps/api/tests/test_ingest.py
git commit -m "feat(ingest): make scanning source-aware"
```

## Task 4: Persist Cheap Thumbnails For Offline Browse

**Files:**

- Create: `apps/api/app/services/thumbnails.py`
- Modify: `apps/api/app/processing/ingest.py`
- Modify: `apps/api/tests/test_ingest.py`
- Modify: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write failing tests for thumbnail persistence**

Cover:

- ingest stores a cheap thumbnail when a supported image is processed
- thumbnail metadata remains available when the source is later marked offline
- search or photo read surfaces enough thumbnail metadata to support later UI work

Keep Phase 1 narrow: one thumbnail size and minimal metadata.

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `uv run python -m pytest apps/api/tests/test_ingest.py apps/api/tests/test_search_service.py -q`

Expected: FAIL because thumbnail persistence is not implemented.

- [ ] **Step 3: Implement thumbnail service**

Create `apps/api/app/services/thumbnails.py` with narrowly scoped responsibilities:

- generate one cheap thumbnail from an image path
- return bytes and simple metadata
- avoid entangling this file with DB writes

- [ ] **Step 4: Wire thumbnail persistence into ingest**

Update `apps/api/app/processing/ingest.py` to:

- attempt thumbnail generation during healthy scans
- persist thumbnail metadata or blob storage references centrally
- treat thumbnail failure as a file-level ingest error, not a source identity failure

- [ ] **Step 5: Run the focused tests to verify pass**

Run: `uv run python -m pytest apps/api/tests/test_ingest.py apps/api/tests/test_search_service.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/thumbnails.py \
  apps/api/app/processing/ingest.py \
  apps/api/tests/test_ingest.py \
  apps/api/tests/test_search_service.py
git commit -m "feat(ingest): persist thumbnails for offline browse"
```

## Task 5: Replace The Operator Contract For Source Registration And Rescan

**Files:**

- Modify: `apps/api/app/cli.py`
- Modify: `apps/cli/cli/queue_client.py`
- Create: `apps/api/app/routers/storage_sources.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_cli.py`
- Test: `apps/cli/tests/test_main.py`
- Test: `apps/cli/tests/test_queue_client.py`
- Test: `apps/api/tests/test_main.py`

- [ ] **Step 1: Write failing CLI and router tests for source-centric commands**

Cover:

- registering a storage source
- adding a watched folder under a source
- rescanning a source or watched folder
- rejecting the old `ingest ... --container-mount-path` contract or downgrading it to development-only compatibility

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `uv run python -m pytest apps/api/tests/test_cli.py apps/cli/tests/test_main.py apps/cli/tests/test_queue_client.py apps/api/tests/test_main.py -q`

Expected: FAIL because the old CLI shape is still hard-coded.

- [ ] **Step 3: Update the API-owned CLI**

Refactor `apps/api/app/cli.py` around commands such as:

- `source register`
- `watched-folder add`
- `ingest rescan`

Keep transitional compatibility only if tests or docs require it.

- [ ] **Step 4: Update the queue client wrapper**

Adjust `apps/cli/cli/queue_client.py` to match the new central contract and stop requiring a local root plus container mount pairing as the primary path.

- [ ] **Step 5: Add a router for storage-source management**

Add `apps/api/app/routers/storage_sources.py` and include it from `apps/api/app/main.py`. Keep the first slice minimal and admin-focused.

- [ ] **Step 6: Run the focused tests to verify pass**

Run: `uv run python -m pytest apps/api/tests/test_cli.py apps/cli/tests/test_main.py apps/cli/tests/test_queue_client.py apps/api/tests/test_main.py -q`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/cli.py \
  apps/cli/cli/queue_client.py \
  apps/api/app/routers/storage_sources.py \
  apps/api/app/main.py \
  apps/api/tests/test_cli.py \
  apps/cli/tests/test_main.py \
  apps/cli/tests/test_queue_client.py \
  apps/api/tests/test_main.py
git commit -m "feat(cli): switch ingest operations to storage sources"
```

## Task 6: Update Phase 1 Documentation And Remove The Container-Mount Mental Model

**Files:**

- Modify: `README.md`
- Modify: `ROADMAP.md`
- Modify: `DESIGN.md`

- [ ] **Step 1: Write the doc updates**

Update the docs so they consistently describe:

- source registration
- marker-file identity
- source-relative watched folders
- central polling
- central thumbnails
- offline-original behavior

Remove or explicitly deprecate guidance that tells operators to supply `--container-mount-path` as the normal ingest workflow.

- [ ] **Step 2: Review the docs against the approved spec**

Check the wording against `docs/superpowers/specs/2026-03-28-storage-source-ingest-architecture-design.md` and confirm the Phase 1 epic language matches the approved architecture.

- [ ] **Step 3: Commit**

```bash
git add README.md ROADMAP.md DESIGN.md
git commit -m "docs: align phase 1 ingest docs with storage sources"
```

## Final Verification

- [ ] **Step 1: Run the full focused verification slice**

Run:

```bash
uv run python -m pytest \
  apps/api/tests/test_schema_definition.py \
  apps/api/tests/test_migrations.py \
  apps/api/tests/test_ingest.py \
  apps/api/tests/test_cli.py \
  apps/api/tests/test_main.py \
  apps/api/tests/test_search_service.py \
  apps/cli/tests/test_main.py \
  apps/cli/tests/test_queue_client.py -q
```

Expected: PASS

- [ ] **Step 2: Review git diff for contract leaks**

Verify there is no remaining product-facing documentation or CLI parsing that treats `container_mount_path` as the normal Phase 1 contract.

- [ ] **Step 3: Create the final integration commit if needed**

```bash
git status --short
git log --oneline -5
```

Ensure the branch history is readable and task-scoped.
