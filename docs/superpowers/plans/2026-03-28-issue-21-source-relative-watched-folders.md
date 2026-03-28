# Issue 21 Source-Relative Watched Folders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add watched-folder management under registered storage sources so folders are stored and validated as source-relative paths instead of free-form scan/container path pairs.

**Architecture:** Introduce a watched-folder service layer beside storage-source registration, then expose a minimal API contract for create/list/enable/disable/remove operations under a source. After the operator-facing contract exists, adapt reconcile/ingest code to resolve existing watched-folder records by `storage_source_id + relative_path` and remove obsolete CLI assumptions that conflict with the new model.

**Tech Stack:** FastAPI, SQLAlchemy Core, pytest, uv

---

### Task 1: Lock watched-folder service behavior with tests

**Files:**
- Modify: `apps/api/tests/test_storage_sources.py`
- Create: `apps/api/app/services/watched_folders.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_create_watched_folder_persists_source_relative_path(...):
    ...


def test_create_watched_folder_rejects_paths_outside_source_boundary(...):
    ...


def test_disable_enable_and_remove_watched_folder(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest apps/api/tests/test_storage_sources.py -v`
Expected: FAIL with missing watched-folder service functions

- [ ] **Step 3: Write minimal implementation**

```python
def create_watched_folder(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest apps/api/tests/test_storage_sources.py -v`
Expected: PASS

### Task 2: Expose watched-folder management through the API

**Files:**
- Create: `apps/api/app/routers/storage_sources.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_main.py`
- Create: `apps/api/tests/test_storage_source_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_create_watched_folder_endpoint(...):
    ...


def test_list_watched_folders_endpoint(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest apps/api/tests/test_storage_source_api.py apps/api/tests/test_main.py -v`
Expected: FAIL with missing router or routes

- [ ] **Step 3: Write minimal router implementation**

```python
router = APIRouter(prefix="/storage-sources", tags=["storage-sources"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest apps/api/tests/test_storage_source_api.py apps/api/tests/test_main.py -v`
Expected: PASS

### Task 3: Switch reconcile/ingest seams to persisted watched folders

**Files:**
- Modify: `apps/api/app/services/file_reconciliation.py`
- Modify: `apps/api/app/processing/ingest.py`
- Modify: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write the failing ingest/reconcile tests**

```python
def test_reconcile_directory_uses_existing_source_relative_watched_folder(...):
    ...


def test_reconcile_directory_rejects_unregistered_source_path(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k watched_folder -v`
Expected: FAIL because reconcile still auto-creates watched folders from raw paths

- [ ] **Step 3: Write minimal implementation**

```python
def resolve_watched_folder_for_scan(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k watched_folder -v`
Expected: PASS

### Task 4: Remove obsolete CLI assumptions and align docs

**Files:**
- Modify: `apps/api/app/cli.py`
- Modify: `apps/cli/tests/test_main.py`
- Modify: `apps/cli/tests/test_queue_client.py`
- Modify: `README.md`

- [ ] **Step 1: Write or update the failing CLI/doc-adjacent tests**

```python
def test_ingest_command_requires_source_based_inputs(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest apps/cli/tests/test_main.py apps/cli/tests/test_queue_client.py -v`
Expected: FAIL with outdated container-mount-path expectations

- [ ] **Step 3: Write minimal implementation**

```python
ingest_parser = subparsers.add_parser("ingest", ...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest apps/cli/tests/test_main.py apps/cli/tests/test_queue_client.py -v`
Expected: PASS

### Task 5: Final verification

**Files:**
- Verify only

- [ ] **Step 1: Run focused verification**

Run: `uv run python -m pytest apps/api/tests/test_storage_sources.py apps/api/tests/test_storage_source_api.py apps/api/tests/test_ingest.py apps/cli/tests/test_main.py apps/cli/tests/test_queue_client.py -v`
Expected: PASS

- [ ] **Step 2: Run full verification**

Run: `uv run python -m pytest`
Expected: PASS
