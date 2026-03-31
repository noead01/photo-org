# Issue 35 Date Range Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make search date range filtering a well-specified typed filter over canonical `shot_ts` with inclusive day boundaries and seed-corpus-backed verification.

**Architecture:** Lock the desired date semantics with failing repository and service tests first, then replace the current raw SQL date-bound construction with typed `datetime` comparisons inside the existing search repository. Finish by verifying the seed-corpus-backed July 2022 search fixture and the broader test suite.

**Tech Stack:** Python, SQLAlchemy, Pydantic, pytest, uv

---

### Task 1: Lock date filter semantics in tests

**Files:**
- Modify: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write failing tests for `from`-only, `to`-only, and bounded date filtering semantics**
- [ ] **Step 2: Write a failing test proving null `shot_ts` rows are excluded when any date filter is applied**
- [ ] **Step 3: Run `uv run --group test python -m pytest apps/api/tests/test_search_service.py -k date_filter -q` and verify the new cases fail for the expected reason**

### Task 2: Implement typed inclusive date bounds

**Files:**
- Modify: `apps/api/app/repositories/photos_repo.py`

- [ ] **Step 1: Replace the raw SQL date-bound interpolation in `PhotosRepository._apply_filters` with typed `datetime` boundary values**
- [ ] **Step 2: Keep `from` inclusive at the start of day and `to` inclusive through the end of day**
- [ ] **Step 3: Re-run `uv run --group test python -m pytest apps/api/tests/test_search_service.py -k date_filter -q` and verify the focused slice passes**

### Task 3: Verify the seed-corpus contract and search slice

**Files:**
- Modify: `seed-corpus/search-fixtures.json` only if the existing July 2022 fixture needs adjustment

- [ ] **Step 1: Confirm the existing July 2022 fixture remains valid under the tightened date semantics**
- [ ] **Step 2: Run `uv run --group test python -m pytest apps/api/tests/test_search_service.py -q` and verify the full search test module passes**
- [ ] **Step 3: Run `uv run --group test python -m pytest -q` if the focused slice remains clean enough to justify broader verification**
