# Issue 24 Source-Relative File Moves Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve logical photo identity by `sha256` while reconciling all valid source-relative file locations for that photo within an accessible storage source.

**Architecture:** Lock the desired semantics with focused polling tests first. Then refactor source-backed reconciliation so `photos` remains content-identity storage and `photo_files` becomes the authoritative set of active, missing, and deleted locations for each photo under accessible sources.

**Tech Stack:** Python, SQLAlchemy Core, pytest, uv

---

### Task 1: Lock multi-location source reconciliation in tests

**Files:**
- Modify: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write the failing test for preserving multiple active locations**
- [ ] **Step 2: Run `uv run python -m pytest apps/api/tests/test_ingest.py -k multiple_locations -q` and verify it fails**
- [ ] **Step 3: Write the failing test for retiring stale locations after an accessible source scan**
- [ ] **Step 4: Run `uv run python -m pytest apps/api/tests/test_ingest.py -k stale_locations -q` and verify it fails**

### Task 2: Reconcile source-relative locations by content identity

**Files:**
- Modify: `apps/api/app/services/file_reconciliation.py`
- Modify: `apps/api/app/processing/ingest.py`

- [ ] **Step 1: Add minimal reconciliation helpers that find existing photos by `sha256` and reconcile per-source file locations**
- [ ] **Step 2: Update the registered-source polling path to reactivate observed locations and retire stale locations within the scanned source**
- [ ] **Step 3: Run the focused tests and verify they pass**

### Task 3: Verify the touched ingest slice

**Files:**
- Modify: `README.md` if touched behavior needs clarification

- [ ] **Step 1: Run `uv run python -m pytest apps/api/tests/test_ingest.py -q` and verify it passes**
- [ ] **Step 2: Run `uv run python -m pytest -q` if the focused slice stays clean enough to justify the broader check**
