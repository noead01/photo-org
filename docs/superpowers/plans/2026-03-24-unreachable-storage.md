# Unreachable Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Distinguish watched-root access failures from healthy path absence so failed scans mark the folder unreachable and never advance file deletion state.

**Architecture:** Keep root-health classification at the scan boundary in `reconcile_directory()`. Healthy scans continue through the existing file lifecycle reconciliation path, while unreachable scans update watched-folder state only and skip file and photo lifecycle mutation.

**Tech Stack:** Python, pytest, SQLAlchemy, SQLite, existing `apps/api` ingest and reconciliation services

---

### Task 1: Add Failing Tests For Unreachable Root Behavior

**Files:**
- Modify: `apps/api/tests/test_ingest.py`
- Test: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_reconcile_directory_marks_watched_folder_unreachable_when_root_scan_fails(...):
    ...


def test_reconcile_directory_does_not_advance_file_lifecycle_when_root_scan_fails(...):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/api/tests/test_ingest.py -k unreachable -v`
Expected: FAIL because `reconcile_directory()` currently always assumes a healthy scan and does not persist unreachable-folder state.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_ingest.py
git commit -m "test(api): cover unreachable watched-folder scans"
```

### Task 2: Classify Root Scan Failures In The Ingest Entry Point

**Files:**
- Modify: `apps/api/app/processing/ingest.py`
- Test: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write the failing test for recovery to healthy state**

```python
def test_reconcile_directory_clears_unreachable_state_after_later_healthy_scan(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_ingest.py::test_reconcile_directory_clears_unreachable_state_after_later_healthy_scan -v`
Expected: FAIL because the scan path has no root-health classification or recovery behavior.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class DirectoryScanResult:
    observed_paths: tuple[Path, ...]
    failure_reason: str | None = None


def scan_watched_root(root: Path) -> DirectoryScanResult:
    try:
        return DirectoryScanResult(observed_paths=tuple(iter_photo_files(root)))
    except FileNotFoundError:
        return DirectoryScanResult(observed_paths=(), failure_reason="folder_unmounted")
    except PermissionError:
        return DirectoryScanResult(observed_paths=(), failure_reason="permission_denied")
    except OSError:
        return DirectoryScanResult(observed_paths=(), failure_reason="io_error")
```

Use that result in `reconcile_directory()` so:

- unreachable scans update watched-folder status and return without calling `reconcile_watched_folder()`
- healthy scans continue through the existing activation and reconciliation flow

- [ ] **Step 4: Run targeted tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_ingest.py -k "unreachable or clears_unreachable_state" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/processing/ingest.py apps/api/tests/test_ingest.py
git commit -m "feat(api): classify unreachable watched-folder scans"
```

### Task 3: Centralize Watched Folder State Updates

**Files:**
- Modify: `apps/api/app/services/file_reconciliation.py`
- Modify: `apps/api/app/processing/ingest.py`
- Test: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write the failing test for preserving last successful scan timestamps on failure**

```python
def test_reconcile_directory_preserves_last_successful_scan_ts_when_root_scan_fails(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_ingest.py::test_reconcile_directory_preserves_last_successful_scan_ts_when_root_scan_fails -v`
Expected: FAIL because watched-folder updates are currently only modeled as healthy scans.

- [ ] **Step 3: Write minimal implementation**

```python
def record_watched_folder_scan_success(...):
    ...


def record_watched_folder_scan_failure(...):
    ...
```

Refactor `ensure_watched_folder()` so folder existence is separate from healthy/failure state mutation.

- [ ] **Step 4: Run targeted tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_ingest.py -k "unreachable or successful_scan_ts" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/file_reconciliation.py apps/api/app/processing/ingest.py apps/api/tests/test_ingest.py
git commit -m "refactor(api): separate watched-folder scan state updates"
```

### Task 4: Verify Healthy Lifecycle Behavior Still Holds

**Files:**
- Modify: `apps/api/tests/test_ingest.py`
- Modify: `apps/api/tests/test_search_service.py`
- Test: `apps/api/tests/test_ingest.py`
- Test: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Add or tighten regression assertions**

```python
def test_reconcile_directory_marks_absent_files_missing(...):
    ...


def test_reconcile_directory_deletes_missing_file_after_grace_period(...):
    ...
```

Add explicit watched-folder assertions where useful so healthy scans still set the folder active.

- [ ] **Step 2: Run targeted regression tests**

Run: `uv run pytest apps/api/tests/test_ingest.py apps/api/tests/test_search_service.py -k "reconcile_directory or soft_deleted" -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_ingest.py apps/api/tests/test_search_service.py
git commit -m "test(api): lock healthy reconciliation regressions"
```

### Task 5: Final Verification And Documentation Check

**Files:**
- Modify: `README.md` (only if a repeatable local verification command needs documentation)
- Test: `apps/api/tests/test_ingest.py`
- Test: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Run the focused verification suite**

Run: `uv run pytest apps/api/tests/test_ingest.py apps/api/tests/test_search_service.py -v`
Expected: PASS

- [ ] **Step 2: Run a representative local reconciliation path**

Run: `uv run pytest apps/api/tests/test_ingest.py -k "reconcile_directory" -v`
Expected: PASS with explicit healthy-scan and unreachable-scan coverage.

- [ ] **Step 3: Update developer-facing docs if needed**

If the new unreachable-scan behavior requires an operator-visible note, document the verification command in `README.md`; otherwise skip this edit.

- [ ] **Step 4: Commit**

```bash
git add apps/api/tests/test_ingest.py apps/api/tests/test_search_service.py README.md
git commit -m "docs(api): document unreachable scan verification"
```
