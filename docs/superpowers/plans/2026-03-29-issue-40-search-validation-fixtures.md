# Issue 40 Search Validation Fixtures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a seed-corpus-backed search fixture catalog and automated validation tests that assert representative supported search scenarios by manifest asset ID.

**Architecture:** Keep fixture data under `seed-corpus/` beside the manifest, then add a test harness that reads the manifest and fixture catalog, prepares searchable records for the checked-in corpus, maps search results back to manifest asset IDs, and asserts supported scenarios end to end at the search layer.

**Tech Stack:** Python, JSON, pytest, SQLAlchemy, uv

---

### Task 1: Inspect the current search and seed-corpus contracts

**Files:**
- Modify: `apps/api/tests/test_search_service.py`
- Create: `seed-corpus/search-fixtures.json`

- [ ] **Step 1: Identify which approved Phase 3 scenarios are executable with the current search request schema and checked-in seed corpus**
- [ ] **Step 2: Write the initial failing structural test that expects a checked-in fixture catalog and validates that every expected asset ID exists in `seed-corpus/manifest.json`**
- [ ] **Step 3: Run `uv run python -m pytest apps/api/tests/test_search_service.py -k fixture_catalog -q` and verify it fails**

### Task 2: Add the seed-corpus fixture catalog

**Files:**
- Create: `seed-corpus/search-fixtures.json`
- Modify: `seed-corpus/README.md` if fixture usage needs documentation

- [ ] **Step 1: Add the minimal fixture catalog for currently supported scenarios using manifest asset IDs and current search request payloads**
- [ ] **Step 2: Re-run `uv run python -m pytest apps/api/tests/test_search_service.py -k fixture_catalog -q` and verify it passes**

### Task 3: Execute fixtures against the search stack

**Files:**
- Modify: `apps/api/tests/test_search_service.py`
- Modify: `apps/api/app/services/search_service.py` only if fixture execution exposes a search-service contract gap

- [ ] **Step 1: Write the failing execution test that loads the manifest and fixture catalog, prepares searchable records for the checked-in corpus, and asserts fixture expectations by manifest asset ID**
- [ ] **Step 2: Run `uv run python -m pytest apps/api/tests/test_search_service.py -k search_fixture_execution -q` and verify it fails**
- [ ] **Step 3: Add the minimal test harness or production-code changes needed to execute fixture-backed assertions cleanly**
- [ ] **Step 4: Re-run `uv run python -m pytest apps/api/tests/test_search_service.py -k search_fixture_execution -q` and verify it passes**

### Task 4: Verify the touched slice

**Files:**
- Modify: `seed-corpus/README.md` if local validation workflow needs explanation

- [ ] **Step 1: Run `uv run python -m pytest apps/api/tests/test_search_service.py -q` and verify the search test module passes**
- [ ] **Step 2: Run `uv run python -m pytest -q` if the focused slice stays clean enough to justify the broader check**
