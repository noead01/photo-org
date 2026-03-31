# Issue 34 Text Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `q` a predictable tokenized text-search clause over photo paths and tags, with AND semantics across query tokens.

**Architecture:** Lock the text-search semantics with failing repository and service tests first, then replace the current single-token fallback with tokenized path/tag matching that requires all non-empty query terms. Keep sort behavior unchanged and verify the existing seed-corpus fixtures still pass.

**Tech Stack:** Python, SQLAlchemy, pytest, uv

---

### Task 1: Lock text-search semantics in tests

**Files:**
- Modify: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write failing tests for multi-token AND semantics across path and tag matches**
- [ ] **Step 2: Write failing tests for case-insensitive matching and whitespace-only query handling**
- [ ] **Step 3: Run `uv run --group test python -m pytest apps/api/tests/test_search_service.py -k text_search -q` and verify the new cases fail for the expected reason**

### Task 2: Implement tokenized path/tag matching

**Files:**
- Modify: `apps/api/app/repositories/photos_repo.py`

- [ ] **Step 1: Replace the current single-token text-query fallback with tokenized matching across `photos.path` and `photo_tags.tag`**
- [ ] **Step 2: Require every non-empty token to match via AND semantics while keeping the query case-insensitive**
- [ ] **Step 3: Treat empty or whitespace-only `q` as no text filter**
- [ ] **Step 4: Re-run `uv run --group test python -m pytest apps/api/tests/test_search_service.py -k text_search -q` and verify the focused slice passes**

### Task 3: Verify the seed-corpus contract and search slice

**Files:**
- Modify: `seed-corpus/search-fixtures.json` only if an additional text-search scenario is required

- [ ] **Step 1: Confirm existing text-search fixtures remain valid under the tightened token semantics**
- [ ] **Step 2: Run `uv run --group test python -m pytest apps/api/tests/test_search_service.py -q` and verify the full search test module passes**
- [ ] **Step 3: Run `uv run --group test python -m pytest -q` if the focused slice remains clean enough to justify broader verification**
