# Issue 38 Facet Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add path-hint filtering and `has_faces` facet breakdown support to the current Phase 3 search stack.

**Architecture:** Extend the typed search request schema with `path_hints`, lock the behavior with failing repository and service tests, then implement minimal query and facet changes inside the existing search repository. Keep the change local to the current search slice so later text-search and date-range work can build on it.

**Tech Stack:** Python, SQLAlchemy, Pydantic, pytest, uv

---

### Task 1: Lock the request and filter semantics in tests

**Files:**
- Modify: `apps/api/tests/test_search_service.py`
- Modify: `apps/api/app/schemas/search_request.py`

- [ ] **Step 1: Write a failing test that validates `SearchFilters` accepts `path_hints` and passes it through to repository calls**
- [ ] **Step 2: Run `uv run python -m pytest apps/api/tests/test_search_service.py -k path_hints -q` and verify it fails**
- [ ] **Step 3: Add the minimal `path_hints` field to `SearchFilters`**
- [ ] **Step 4: Re-run `uv run python -m pytest apps/api/tests/test_search_service.py -k path_hints -q` and verify it passes**

### Task 2: Implement repository filtering for path hints and boolean face filters

**Files:**
- Modify: `apps/api/tests/test_search_service.py`
- Modify: `apps/api/app/repositories/photos_repo.py`

- [ ] **Step 1: Write failing repository tests for `path_hints` filtering and for combining `path_hints` with `has_faces=false`**
- [ ] **Step 2: Run `uv run python -m pytest apps/api/tests/test_search_service.py -k \"path_hints or has_faces\" -q` and verify the new cases fail for the expected reason**
- [ ] **Step 3: Implement minimal query changes in `PhotosRepository._apply_filters` so `path_hints` uses `ANY` semantics within the field and composes with existing filters using `AND`**
- [ ] **Step 4: Re-run `uv run python -m pytest apps/api/tests/test_search_service.py -k \"path_hints or has_faces\" -q` and verify the focused slice passes**

### Task 3: Add `has_faces` facet output

**Files:**
- Modify: `apps/api/tests/test_search_service.py`
- Modify: `apps/api/app/domain/facets.py`
- Modify: `apps/api/app/repositories/photos_repo.py`

- [ ] **Step 1: Write a failing test that expects `compute_facets` to return a `has_faces` breakdown over the filtered photo set**
- [ ] **Step 2: Run `uv run python -m pytest apps/api/tests/test_search_service.py -k has_faces_facet -q` and verify it fails**
- [ ] **Step 3: Add the minimal facet implementation and response formatting needed to produce the `has_faces` counts**
- [ ] **Step 4: Re-run `uv run python -m pytest apps/api/tests/test_search_service.py -k has_faces_facet -q` and verify it passes**

### Task 4: Verify the search slice and seed-corpus contract

**Files:**
- Modify: `seed-corpus/search-fixtures.json` only if a new supported fixture is needed

- [ ] **Step 1: Add or update a seed-corpus-backed fixture for a path-hint search if the current catalog does not already cover the new typed filter contract**
- [ ] **Step 2: Run `uv run python -m pytest apps/api/tests/test_search_service.py -q` and verify the full search test module passes**
- [ ] **Step 3: Run `uv run python -m pytest -q` if the focused slice remains clean enough to justify the broader verification**
