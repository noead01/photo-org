# Core Catalog Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define a canonical shared Phase 0 database schema for the core catalog and labeling entities without absorbing the broader shared access-layer work.

**Architecture:** Add a new shared schema package that owns SQLAlchemy metadata and table definitions, then repoint the current API schema bootstrap to use that package. Keep implementation PostgreSQL-first while preserving SQLite compatibility for narrow tests and schema verification.

**Tech Stack:** Python 3.12, uv workspace, SQLAlchemy 2.x, pgvector, pytest

---

## File Structure

- Create `packages/db-schema/pyproject.toml` for the new workspace package metadata
- Create `packages/db-schema/photoorg_db_schema/__init__.py` to expose metadata and table objects
- Create `packages/db-schema/photoorg_db_schema/schema.py` for the canonical SQLAlchemy metadata, helpers, tables, and indexes
- Modify `pyproject.toml` to include the new package in the workspace
- Modify `apps/api/pyproject.toml` to depend on the shared schema package
- Modify `apps/api/app/storage.py` to import schema definitions from the new package instead of defining tables locally
- Add `apps/api/tests/test_schema_definition.py` for focused schema verification
- Update existing schema tests only where the new canonical schema changes expectations

### Task 1: Add a failing schema-definition test

**Files:**
- Create: `apps/api/tests/test_schema_definition.py`

- [ ] **Step 1: Write the failing test**

```python
def test_phase_zero_schema_exposes_expected_tables():
    expected = {
        "photos",
        "photo_files",
        "faces",
        "people",
        "face_labels",
        "watched_folders",
        "ingest_runs",
    }
    assert expected.issubset(metadata.tables.keys())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_schema_definition.py -q`
Expected: FAIL because the current schema module does not define the Phase 0 table set.

- [ ] **Step 3: Write minimal implementation**

Create the shared schema package skeleton and expose shared metadata/table names.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest apps/api/tests/test_schema_definition.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml apps/api/pyproject.toml packages/db-schema apps/api/tests/test_schema_definition.py
git commit -m "feat(db): add shared phase zero schema package"
```

### Task 2: Add failing constraint and bootstrap tests

**Files:**
- Modify: `apps/api/tests/test_schema_definition.py`
- Modify: `apps/api/app/storage.py`

- [ ] **Step 1: Write the failing tests**

Add tests that verify:

- `photos.sha256` is unique
- `photo_files.photo_id` and `faces.photo_id` have foreign keys to `photos`
- `watched_folders.root_path` is unique
- `ensure_schema()` creates all expected Phase 0 tables in SQLite

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/api/tests/test_schema_definition.py -q`
Expected: FAIL because the canonical schema and bootstrap import path are incomplete.

- [ ] **Step 3: Write minimal implementation**

Move canonical table definitions into `packages/db-schema/photoorg_db_schema/schema.py` and update `apps/api/app/storage.py` to import them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_schema_definition.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/storage.py packages/db-schema/photoorg_db_schema/schema.py apps/api/tests/test_schema_definition.py
git commit -m "feat(db): define phase zero schema constraints"
```

### Task 3: Reconcile existing schema tests with the new canonical model

**Files:**
- Modify: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write or adjust the failing test expectations**

Update the schema bootstrap assertion so it verifies the canonical tables rather than the old API-local subset.

- [ ] **Step 2: Run focused tests to verify the failure**

Run: `uv run pytest apps/api/tests/test_ingest.py -q`
Expected: FAIL where the old schema assumptions no longer match.

- [ ] **Step 3: Write minimal implementation**

Adjust the existing schema bootstrap surface or test expectations so the canonical schema remains authoritative without forcing the full ingest rewrite into this issue.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_ingest.py apps/api/tests/test_schema_definition.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/test_ingest.py apps/api/tests/test_schema_definition.py apps/api/app/storage.py
git commit -m "test(api): align schema checks with shared model"
```

### Task 4: Run targeted validation and summarize residual gaps

**Files:**
- Modify: `docs/superpowers/specs/2026-03-21-core-catalog-schema-design.md` if implementation requires a small clarification

- [ ] **Step 1: Run targeted validation**

Run: `uv run pytest apps/api/tests/test_schema_definition.py apps/api/tests/test_ingest.py -q`
Expected: PASS

- [ ] **Step 2: Run a broader smoke test if the environment allows**

Run: `uv run pytest apps/api/tests -q`
Expected: PASS or a clearly documented pre-existing/environmental failure.

- [ ] **Step 3: Review the diff for scope discipline**

Confirm the issue only establishes canonical schema definitions and bootstrap integration, not a full data-layer rewrite.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-03-21-core-catalog-schema-design.md
git commit -m "docs(db): record phase zero schema design"
```
