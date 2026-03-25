# Missing File Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement conservative file-instance missing and soft-delete reconciliation with a global grace period, and exclude logically deleted photos from default search results.

**Architecture:** Add a dedicated reconciliation service around `photo_files` so healthy watched-folder scans can update lifecycle state independently from queue transport concerns. Keep `photos` as the logical parent record, derive `photos.deleted_ts` from related file-instance state, and thread a global grace-period config through the reconciliation path.

**Tech Stack:** Python, SQLAlchemy Core, FastAPI app modules, pytest, SQLite-backed migration tests

---

### Task 1: Add Failing Tests For Reconciliation Lifecycle Rules

**Files:**
- Modify: `apps/api/tests/test_ingest.py`
- Reference: `apps/api/app/processing/ingest.py`
- Reference: `apps/api/app/storage.py`

- [ ] **Step 1: Write the failing reconciliation lifecycle tests**

```python
def test_reconcile_directory_marks_absent_files_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_root = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-missing.db'}"
    upgrade_database(db_url)

    reconcile_directory(staged_root, database_url=db_url)
    target = staged_root / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    target.unlink()

    reconcile_directory(staged_root, database_url=db_url)

    row = load_photo_file_row(db_url, "seed-corpus/family-events/birthday-park/birthday_park_006.jpg")
    assert row["lifecycle_state"] == "missing"
    assert row["missing_ts"] is not None
    assert row["deleted_ts"] is None


def test_reconcile_directory_deletes_missing_file_after_grace_period(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_root = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-deleted.db'}"
    upgrade_database(db_url)

    first_seen = datetime(2026, 3, 24, tzinfo=UTC)
    reconcile_directory(staged_root, database_url=db_url, now=first_seen)
    target = staged_root / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    target.unlink()

    reconcile_directory(staged_root, database_url=db_url, now=first_seen)
    reconcile_directory(
        staged_root,
        database_url=db_url,
        now=first_seen + timedelta(days=1, seconds=1),
    )

    row = load_photo_file_row(db_url, "seed-corpus/family-events/birthday-park/birthday_park_006.jpg")
    assert row["lifecycle_state"] == "deleted"
    assert row["deleted_ts"] is not None
```

- [ ] **Step 2: Run the targeted lifecycle tests to verify they fail**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_ingest.py -q`
Expected: FAIL because `reconcile_directory()` and `photo_files` lifecycle persistence do not exist yet.

- [ ] **Step 3: Add any small test helpers needed for `photo_files` inspection**

Add minimal helpers to `apps/api/tests/test_ingest.py` for:

- reading `photo_files` rows by relative path
- reading `photos.deleted_ts`
- controlling reconciliation timestamps in tests

Do not implement reconciliation logic yet.

- [ ] **Step 4: Re-run the targeted lifecycle tests to verify the intended RED state**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_ingest.py -q`
Expected: FAIL specifically on missing reconciliation behavior rather than helper or import errors.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/test_ingest.py
git commit -m "test(api): define missing file lifecycle expectations"
```

### Task 2: Implement The Reconciliation Service And Global Grace-Period Config

**Files:**
- Modify: `apps/api/app/db/config.py`
- Modify: `apps/api/app/processing/ingest.py`
- Modify: `apps/api/app/storage.py`
- Create: `apps/api/app/services/file_reconciliation.py`
- Test: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write one focused failing test for zero-day grace period**

```python
def test_reconcile_directory_with_zero_day_grace_immediately_deletes_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_root = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-zero-grace.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 24, tzinfo=UTC)
    reconcile_directory(staged_root, database_url=db_url, now=now, missing_file_grace_period_days=0)
    target = staged_root / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    target.unlink()

    reconcile_directory(staged_root, database_url=db_url, now=now, missing_file_grace_period_days=0)

    row = load_photo_file_row(db_url, "seed-corpus/family-events/birthday-park/birthday_park_006.jpg")
    assert row["lifecycle_state"] == "deleted"
```

- [ ] **Step 2: Run the zero-grace test to verify it fails**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_ingest.py::test_reconcile_directory_with_zero_day_grace_immediately_deletes_missing_file -q`
Expected: FAIL because the grace-period config and reconciliation policy are not implemented.

- [ ] **Step 3: Implement minimal reconciliation and config support**

Implement:

- `resolve_missing_file_grace_period_days()` in `apps/api/app/db/config.py`
- `file_reconciliation.py` with focused functions for:
  - activating observed file rows
  - marking absent rows missing
  - promoting eligible missing rows to deleted
  - recomputing parent `photos.deleted_ts`
- `reconcile_directory()` in `apps/api/app/processing/ingest.py` to:
  - enumerate supported files
  - ensure observed files have `photos` and `photo_files` records
  - pass the observed relative-path set plus timestamp into the reconciliation service
- `app/storage.py` exports needed by the new service for `photo_files` access

Keep the implementation minimal:

- use one watched-root scope identified by the directory path being reconciled
- create or reuse one `watched_folders` row for that root
- clear `missing_ts`, `deleted_ts`, and `absence_reason` on reappearance
- treat `0` grace days as immediate deletion in the same healthy pass

- [ ] **Step 4: Run the lifecycle-focused ingest tests to verify they pass**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_ingest.py -q`
Expected: PASS for the new reconciliation lifecycle tests and existing ingest queue tests.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/db/config.py apps/api/app/processing/ingest.py apps/api/app/services/file_reconciliation.py apps/api/app/storage.py apps/api/tests/test_ingest.py
git commit -m "feat(api): reconcile missing files conservatively"
```

### Task 3: Add Failing Tests For Logical Photo Soft Delete And Recovery

**Files:**
- Modify: `apps/api/tests/test_ingest.py`
- Reference: `apps/api/app/services/file_reconciliation.py`

- [ ] **Step 1: Write the failing logical-photo lifecycle tests**

```python
def test_photo_is_soft_deleted_only_when_all_file_instances_are_deleted(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'photo-soft-delete.db'}"
    upgrade_database(database_url)

    seed_photo_with_two_file_instances(database_url)
    now = datetime(2026, 3, 24, tzinfo=UTC)

    reconcile_photo_file_states(
        database_url,
        observed_paths={"watched/photo-a.jpg"},
        missing_file_grace_period_days=0,
        now=now,
    )

    assert load_photo_deleted_ts(database_url, "photo-1") is None


def test_reappearing_file_clears_parent_photo_deleted_timestamp(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'photo-recover.db'}"
    upgrade_database(database_url)

    seed_deleted_photo_with_file_instance(database_url)

    reconcile_photo_file_states(
        database_url,
        observed_paths={"watched/photo-a.jpg"},
        missing_file_grace_period_days=0,
        now=datetime(2026, 3, 24, tzinfo=UTC),
    )

    assert load_photo_deleted_ts(database_url, "photo-1") is None
```

- [ ] **Step 2: Run the focused logical-photo tests to verify they fail**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_ingest.py -q`
Expected: FAIL because parent `photos.deleted_ts` is not yet derived consistently from `photo_files`.

- [ ] **Step 3: Implement minimal parent-photo soft-delete aggregation**

Update the reconciliation service so:

- parent photo deletion is recomputed for every photo touched by observed or absent file-instance changes
- `photos.deleted_ts` is set only when all related file instances are `deleted`
- `photos.deleted_ts` is cleared if any related file instance returns to `active` or `missing`

Keep the aggregation local to the reconciliation module rather than duplicating it elsewhere.

- [ ] **Step 4: Re-run the focused ingest tests to verify logical-photo behavior passes**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_ingest.py -q`
Expected: PASS for the logical-photo deletion and recovery scenarios.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/file_reconciliation.py apps/api/tests/test_ingest.py
git commit -m "feat(api): derive logical photo soft deletes from file state"
```

### Task 4: Filter Soft-Deleted Photos Out Of Default Search Results

**Files:**
- Modify: `apps/api/tests/test_search_service.py`
- Modify: `apps/api/tests/test_main.py`
- Modify: `apps/api/app/repositories/photos_repo.py`
- Test: `apps/api/tests/test_search_service.py`
- Test: `apps/api/tests/test_main.py`

- [ ] **Step 1: Write the failing search coverage**

```python
def test_search_repository_excludes_soft_deleted_photos_by_default(session):
    repo = PhotosRepository(session)
    seed_search_photo(session, photo_id="active-photo", deleted_ts=None)
    seed_search_photo(session, photo_id="deleted-photo", deleted_ts=datetime(2026, 3, 24, tzinfo=UTC))

    items, total, cursor = repo.search_photos(
        filters=SearchFilters(),
        sort=SortSpec(by="shot_ts", dir="desc"),
        page=PageSpec(limit=50),
    )

    assert [item["photo_id"] for item in items] == ["active-photo"]
    assert total == 1
```

- [ ] **Step 2: Run the targeted search tests to verify they fail**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_search_service.py apps/api/tests/test_main.py -q`
Expected: FAIL because default repository queries still include photos where `deleted_ts` is non-null.

- [ ] **Step 3: Implement the minimal repository filter**

Update `PhotosRepository` so:

- the base search query excludes `photos.deleted_ts IS NOT NULL`
- filtered photo ID queries for facets exclude soft-deleted photos too

Do not add a user-facing override in this issue.

- [ ] **Step 4: Re-run the targeted search tests to verify they pass**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_search_service.py apps/api/tests/test_main.py -q`
Expected: PASS with deleted photos omitted from default results and counts.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/repositories/photos_repo.py apps/api/tests/test_search_service.py apps/api/tests/test_main.py
git commit -m "feat(api): hide soft deleted photos from search"
```

### Task 5: Add A Repeatable End-To-End Verification Path And Finish Validation

**Files:**
- Modify: `apps/api/tests/test_ingest.py`
- Modify: `CONTRIBUTING.md`
- Reference: `docs/superpowers/specs/2026-03-24-missing-file-lifecycle-design.md`

- [ ] **Step 1: Write the failing documentation or end-to-end verification assertion**

```python
def test_contributing_mentions_missing_file_reconciliation_verification_path():
    contributing = Path("CONTRIBUTING.md").read_text()

    assert "missing-file reconciliation" in contributing
    assert "PYTHONPATH=apps/api uv run pytest apps/api/tests/test_ingest.py -q" in contributing
```

- [ ] **Step 2: Run the focused verification tests to verify they fail**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_ingest.py apps/api/tests/test_seed_corpus_manifest.py -q`
Expected: FAIL because the verification path is not documented yet.

- [ ] **Step 3: Add the minimal contributor-facing verification note**

Document in `CONTRIBUTING.md`:

- the targeted pytest command that exercises missing-file lifecycle behavior
- that the test uses a temporary watched-folder fixture and simulated time to verify missing, deleted, and recovery transitions

Do not add broader worker-operation documentation in this issue.

- [ ] **Step 4: Run the full validation slice**

Run:

- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_ingest.py -q`
- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_search_service.py apps/api/tests/test_main.py -q`

Expected:

- PASS for the reconciliation and search suites
- PASS for the representative watched-folder verification path

- [ ] **Step 5: Commit**

```bash
git add CONTRIBUTING.md apps/api/tests/test_ingest.py apps/api/tests/test_search_service.py apps/api/tests/test_main.py
git commit -m "docs(api): document missing file lifecycle verification"
```
