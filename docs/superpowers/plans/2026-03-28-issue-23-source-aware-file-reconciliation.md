# Issue 23 Source-Aware File Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make source-backed ingest and reconciliation derive stable file identity from registered source ownership and source-relative paths, while removing touched legacy container-path assumptions.

**Architecture:** Lock the new behavior with focused ingest tests first, then refactor the source-backed polling path so canonical photo identity no longer depends on alias or container path spellings. Keep missing-file behavior conservative by preserving the existing source-validation gate and limit cleanup to the files touched by this slice.

**Tech Stack:** Python, SQLAlchemy Core, pytest, uv

---

## File Map

- Modify: `apps/api/app/processing/ingest.py`
- Modify: `apps/api/app/services/file_reconciliation.py`
- Modify: `apps/api/app/db/ingest_runs.py`
- Modify: `apps/api/tests/test_ingest.py`
- Modify: `README.md`

### Task 1: Lock source-aware identity in tests

**Files:**
- Modify: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write the failing tests**

Add focused tests covering:

- source-backed polling through two aliases keeps the same canonical `photos.path` and `photo_id`
- a changed file in a registered watched folder updates the existing logical photo instead of creating alias-specific duplicates
- source-backed polling no longer needs container-path-derived expectations in the touched assertions/helpers

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k "storage_sources or alias or changed" -q`
Expected: FAIL because source-backed identity still depends on alias/container-style paths.

### Task 2: Refactor source-backed ingest and reconciliation

**Files:**
- Modify: `apps/api/app/processing/ingest.py`
- Modify: `apps/api/app/services/file_reconciliation.py`
- Modify: `apps/api/app/db/ingest_runs.py`

- [ ] **Step 1: Implement minimal source-aware canonical path helpers**

Refactor the source-backed polling path to build canonical logical paths from:

- `storage_source_id`
- persisted watched-folder `relative_path`
- file path relative to the watched folder root

Keep the legacy one-shot ingest/reconcile entry points working unless the touched code can be simplified safely.

- [ ] **Step 2: Remove touched legacy container-path references**

Delete or stop using container-path plumbing in the source-backed polling path where the validated source context already provides the needed identity inputs.

- [ ] **Step 3: Run the focused tests to verify pass**

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k "storage_sources or alias or changed" -q`
Expected: PASS

### Task 3: Update docs and run verification

**Files:**
- Modify: `README.md`
- Modify: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Update touched docs**

Adjust the README only where it still implies that source-backed reconciliation identity comes from container-mount paths.

- [ ] **Step 2: Run targeted verification**

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -q`
Expected: PASS

- [ ] **Step 3: Run full verification**

Run: `uv run python -m pytest -q`
Expected: PASS
