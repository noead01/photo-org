# Storage Source Incremental Polling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make routine `POST /api/v1/internal/storage-sources/poll` calls default to fast incremental discovery while preserving an explicit full reconciliation path for deletion and missing-file lifecycle updates.

**Architecture:** Add an explicit polling mode contract that flows from the internal API endpoint through the storage-source polling service into `poll_registered_storage_sources()`. Keep chunked file discovery and queue idempotency unchanged, but split watched-folder finalization into an incremental success path and a full reconciliation path so routine polls skip end-of-scan missing-file reconciliation.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy Core, pytest, SQLite test databases

---

## File Structure

- Modify: `apps/api/app/routers/ingest_queue.py`
  - Extend the internal poll request model with an explicit `poll_mode` field and forward it to the service.
- Modify: `apps/api/app/services/storage_source_polling.py`
  - Thread the new mode through `trigger_storage_source_polling()` into `poll_registered_storage_sources()`.
- Modify: `apps/api/app/processing/ingest_polling.py`
  - Define the poll-mode contract, make incremental the default, and split watched-folder finalization so only full mode runs missing-file reconciliation.
- Modify: `apps/api/tests/test_ingest_queue_api.py`
  - Add API coverage for the new default and explicit full-mode forwarding.
- Modify: `apps/api/tests/test_storage_source_polling_service.py`
  - Add service coverage that the selected poll mode is forwarded correctly.
- Modify: `apps/api/tests/test_ingest_polling.py`
  - Add focused polling tests for incremental-vs-full reconciliation behavior.
- Modify: `README.md`
  - Clarify that routine internal polling is incremental by default and full reconciliation is explicit.
- Modify: `CONTRIBUTING.md`
  - Update worker examples for the internal polling endpoint to document `poll_mode`.

### Task 1: Lock The API And Service Contract With Failing Tests

**Files:**
- Modify: `apps/api/tests/test_ingest_queue_api.py`
- Modify: `apps/api/tests/test_storage_source_polling_service.py`
- Modify: `apps/api/app/routers/ingest_queue.py`
- Modify: `apps/api/app/services/storage_source_polling.py`

- [ ] **Step 1: Write the failing API tests for default and explicit poll-mode forwarding**

```python
def test_poll_storage_sources_endpoint_defaults_to_incremental_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    class Result:
        scanned = 1
        enqueued = 1
        inserted = 0
        updated = 0
        queue_processed = 0
        queue_failed = 0
        queue_retryable_errors = 0
        poll_errors = ()
        error_count = 0

    def fake_trigger_storage_source_polling(
        *,
        queue_process_limit: int = 100,
        drain_queue: bool = True,
        poll_mode: str = "incremental",
    ):
        captured["queue_process_limit"] = queue_process_limit
        captured["drain_queue"] = drain_queue
        captured["poll_mode"] = poll_mode
        return Result()

    monkeypatch.setattr(
        "app.routers.ingest_queue.trigger_storage_source_polling",
        fake_trigger_storage_source_polling,
    )

    response = client.post(
        "/api/v1/internal/storage-sources/poll",
        headers={"X-Worker-Role": "ingest-processor"},
        json={},
    )

    assert response.status_code == 200
    assert captured == {
        "queue_process_limit": 100,
        "drain_queue": True,
        "poll_mode": "incremental",
    }


def test_poll_storage_sources_endpoint_forwards_explicit_full_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    class Result:
        scanned = 10
        enqueued = 7
        inserted = 3
        updated = 2
        queue_processed = 5
        queue_failed = 1
        queue_retryable_errors = 2
        poll_errors = ("marker mismatch",)
        error_count = 4

    def fake_trigger_storage_source_polling(
        *,
        queue_process_limit: int = 100,
        drain_queue: bool = True,
        poll_mode: str = "incremental",
    ):
        captured["queue_process_limit"] = queue_process_limit
        captured["drain_queue"] = drain_queue
        captured["poll_mode"] = poll_mode
        return Result()

    monkeypatch.setattr(
        "app.routers.ingest_queue.trigger_storage_source_polling",
        fake_trigger_storage_source_polling,
    )

    response = client.post(
        "/api/v1/internal/storage-sources/poll",
        headers={"X-Worker-Role": "ingest-processor"},
        json={"queue_process_limit": 333, "drain_queue": False, "poll_mode": "full"},
    )

    assert response.status_code == 200
    assert captured == {
        "queue_process_limit": 333,
        "drain_queue": False,
        "poll_mode": "full",
    }
```

- [ ] **Step 2: Run the API test slice to verify it fails**

Run: `uv run python -m pytest apps/api/tests/test_ingest_queue_api.py -k "poll_storage_sources_endpoint" -q`

Expected: FAIL because `fake_trigger_storage_source_polling()` is not called with a `poll_mode` argument and the request model rejects or ignores the new field.

- [ ] **Step 3: Write the failing service test for poll-mode forwarding**

```python
def test_trigger_storage_source_polling_forwards_poll_mode(monkeypatch):
    captured: dict[str, object] = {}
    photo_counts = iter([11, 11])

    def fake_poll_registered_storage_sources(**kwargs):
        captured["database_url"] = kwargs.get("database_url")
        captured["poll_mode"] = kwargs.get("poll_mode")
        return type(
            "PollResult",
            (),
            {
                "scanned": 4,
                "enqueued": 4,
                "updated": 0,
                "errors": [],
            },
        )()

    monkeypatch.setattr(
        polling_service,
        "poll_registered_storage_sources",
        fake_poll_registered_storage_sources,
    )
    monkeypatch.setattr(
        polling_service,
        "_count_photos",
        lambda database_url=None: next(photo_counts),
    )

    result = polling_service.trigger_storage_source_polling(
        queue_process_limit=77,
        drain_queue=False,
        poll_mode="full",
    )

    assert captured["poll_mode"] == "full"
    assert result.scanned == 4
    assert result.enqueued == 4
```

- [ ] **Step 4: Run the service test slice to verify it fails**

Run: `uv run python -m pytest apps/api/tests/test_storage_source_polling_service.py -q`

Expected: FAIL because `trigger_storage_source_polling()` does not yet accept or forward `poll_mode`.

- [ ] **Step 5: Implement the minimal API and service contract**

```python
class TriggerStorageSourcePollingRequest(BaseModel):
    queue_process_limit: int = Field(default=100, ge=1, le=1000)
    drain_queue: bool = Field(default=True)
    poll_mode: Literal["incremental", "full"] = Field(
        default="incremental",
        description="Select incremental discovery or full missing-file reconciliation.",
    )


def trigger_storage_source_polling(
    *,
    database_url: str | Path | None = None,
    queue_process_limit: int = 100,
    drain_queue: bool = True,
    poll_mode: str = "incremental",
) -> TriggerStorageSourcePollingResult:
    initial_photo_count = _count_photos(database_url)
    poll_result = poll_registered_storage_sources(
        database_url=database_url,
        poll_mode=poll_mode,
    )
```

```python
return trigger_storage_source_polling(
    queue_process_limit=body.queue_process_limit,
    drain_queue=body.drain_queue,
    poll_mode=body.poll_mode,
)
```

- [ ] **Step 6: Run the API and service tests to verify they pass**

Run: `uv run python -m pytest apps/api/tests/test_ingest_queue_api.py -k "poll_storage_sources_endpoint" -q`

Expected: PASS

Run: `uv run python -m pytest apps/api/tests/test_storage_source_polling_service.py -q`

Expected: PASS

- [ ] **Step 7: Commit the contract changes**

```bash
git add apps/api/app/routers/ingest_queue.py apps/api/app/services/storage_source_polling.py apps/api/tests/test_ingest_queue_api.py apps/api/tests/test_storage_source_polling_service.py
git commit -m "feat: add poll mode contract"
```

### Task 2: Add Failing Poller Tests For Incremental And Full Finalization

**Files:**
- Modify: `apps/api/tests/test_ingest_polling.py`
- Modify: `apps/api/app/processing/ingest_polling.py`

- [ ] **Step 1: Write the failing incremental-vs-full poller tests**

```python
def test_poll_registered_storage_sources_incremental_mode_skips_missing_reconciliation(tmp_path):
    from app.processing.ingest_polling import poll_registered_storage_sources

    database_url = f"sqlite:///{tmp_path / 'poll-incremental-skip-reconcile.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 6, 8, 12, 0, tzinfo=UTC)

    root = tmp_path / "source-root"
    watched = root / "imports"
    watched.mkdir(parents=True)
    first_photo = watched / "photo_000.jpg"
    second_photo = watched / "photo_001.jpg"
    _write_test_image(first_photo)
    _write_test_image(second_photo)

    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Source",
            marker_filename=MARKER_FILENAME,
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            now=now,
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            watched_path=watched.as_posix(),
            display_name="Imports",
            now=now,
        )
        write_source_marker(root, storage_source_id=source["storage_source_id"])

    poll_registered_storage_sources(database_url=database_url, now=now, poll_mode="full")
    second_photo.unlink()

    later = now.replace(hour=13)
    result = poll_registered_storage_sources(
        database_url=database_url,
        now=later,
        poll_mode="incremental",
    )

    assert result.errors == []
    with engine.connect() as connection:
        row = connection.execute(
            select(
                photo_files.c.lifecycle_state,
                photo_files.c.missing_ts,
                photo_files.c.deleted_ts,
            ).where(
                photo_files.c.watched_folder_id == watched_folder["watched_folder_id"],
                photo_files.c.relative_path == "photo_001.jpg",
            )
        ).mappings().one()
    assert row["lifecycle_state"] == "active"
    assert row["missing_ts"] is None
    assert row["deleted_ts"] is None


def test_poll_registered_storage_sources_full_mode_marks_missing_files(tmp_path):
    from app.processing.ingest_polling import poll_registered_storage_sources

    database_url = f"sqlite:///{tmp_path / 'poll-full-reconcile.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 6, 8, 12, 0, tzinfo=UTC)

    root = tmp_path / "source-root"
    watched = root / "imports"
    watched.mkdir(parents=True)
    first_photo = watched / "photo_000.jpg"
    second_photo = watched / "photo_001.jpg"
    _write_test_image(first_photo)
    _write_test_image(second_photo)

    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Source",
            marker_filename=MARKER_FILENAME,
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            now=now,
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            watched_path=watched.as_posix(),
            display_name="Imports",
            now=now,
        )
        write_source_marker(root, storage_source_id=source["storage_source_id"])

    poll_registered_storage_sources(database_url=database_url, now=now, poll_mode="full")
    second_photo.unlink()

    later = now.replace(hour=13)
    result = poll_registered_storage_sources(
        database_url=database_url,
        now=later,
        poll_mode="full",
        missing_file_grace_period_days=0,
    )

    assert result.errors == []
    with engine.connect() as connection:
        row = connection.execute(
            select(
                photo_files.c.lifecycle_state,
                photo_files.c.missing_ts,
                photo_files.c.deleted_ts,
            ).where(
                photo_files.c.watched_folder_id == watched_folder["watched_folder_id"],
                photo_files.c.relative_path == "photo_001.jpg",
            )
        ).mappings().one()
    assert row["lifecycle_state"] == "deleted"
    assert row["missing_ts"] == later.replace(tzinfo=None)
    assert row["deleted_ts"] == later.replace(tzinfo=None)
```

- [ ] **Step 2: Run the poller test slice to verify it fails**

Run: `uv run python -m pytest apps/api/tests/test_ingest_polling.py -k "incremental_mode_skips_missing_reconciliation or full_mode_marks_missing_files" -q`

Expected: FAIL because `poll_registered_storage_sources()` does not yet accept `poll_mode`.

- [ ] **Step 3: Add the poll-mode contract and split finalization in the poller**

```python
PollMode = Literal["incremental", "full"]


def poll_registered_storage_sources(
    database_url: str | Path | None = None,
    *,
    now: datetime | None = None,
    missing_file_grace_period_days: int | None = None,
    poll_chunk_size: int = 100,
    poll_mode: PollMode = "incremental",
) -> IngestResult:
    _validate_chunk_size(poll_chunk_size)
    _validate_poll_mode(poll_mode)
```

```python
if poll_mode == "full":
    observed_relative_paths: set[str] | None = set()
else:
    observed_relative_paths = None

for chunk_paths in _iter_chunks(iter_photo_files(scan_root), chunk_size=poll_chunk_size):
    with engine.begin() as connection:
        outcome, chunk_touched_photo_ids = _process_watched_folder_chunk(
            connection,
            watched_folder_id=target.watched_folder_id,
            source_root=scan_root,
            photo_paths=chunk_paths,
            canonical_path_for_relative_path=_registered_source_path_builder(
                storage_source_id=source_target.storage_source_id,
                watched_folder_relative_path=target.relative_path,
            ),
            reuse_existing_photo_by_sha=True,
            now=at,
            observed_relative_paths=observed_relative_paths,
            queue_store=queue_store,
            storage_source_id=source_target.storage_source_id,
        )
```

```python
def _finalize_incremental_watched_folder_scan(
    connection: Connection,
    *,
    watched_folder_id: str,
    now: datetime,
) -> None:
    record_watched_folder_scan_success(
        connection,
        watched_folder_id=watched_folder_id,
        now=now,
    )


def _finalize_full_watched_folder_scan(
    connection: Connection,
    *,
    watched_folder_id: str,
    observed_relative_paths: set[str],
    touched_photo_ids: set[str],
    now: datetime,
    missing_file_grace_period_days: int,
) -> None:
    touched_photo_ids.update(
        reconcile_watched_folder(
            connection,
            watched_folder_id=watched_folder_id,
            observed_relative_paths=observed_relative_paths,
            now=now,
            missing_file_grace_period_days=missing_file_grace_period_days,
        )
    )
    refresh_photo_deleted_timestamps(connection, photo_ids=touched_photo_ids, now=now)
    record_watched_folder_scan_success(
        connection,
        watched_folder_id=watched_folder_id,
        now=now,
    )
```

- [ ] **Step 4: Run the focused poller tests to verify they pass**

Run: `uv run python -m pytest apps/api/tests/test_ingest_polling.py -k "incremental_mode_skips_missing_reconciliation or full_mode_marks_missing_files" -q`

Expected: PASS

- [ ] **Step 5: Commit the poller mode split**

```bash
git add apps/api/app/processing/ingest_polling.py apps/api/tests/test_ingest_polling.py
git commit -m "feat: split incremental and full polling"
```

### Task 3: Regress Existing Polling Behavior Around Default Incremental Mode

**Files:**
- Modify: `apps/api/tests/test_ingest_polling.py`
- Modify: `apps/api/tests/test_ingest.py`
- Modify: `apps/api/app/processing/ingest_polling.py`

- [ ] **Step 1: Update or add tests that lock in the new default**

```python
def test_poll_registered_storage_sources_defaults_to_incremental_mode(tmp_path):
    from app.processing.ingest_polling import poll_registered_storage_sources

    database_url = f"sqlite:///{tmp_path / 'poll-default-incremental.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)

    root = tmp_path / "source-root"
    watched = root / "imports"
    watched.mkdir(parents=True)
    first_photo = watched / "photo_000.jpg"
    second_photo = watched / "photo_001.jpg"
    _write_test_image(first_photo)
    _write_test_image(second_photo)

    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Source",
            marker_filename=MARKER_FILENAME,
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            now=now,
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            watched_path=watched.as_posix(),
            display_name="Imports",
            now=now,
        )
        write_source_marker(root, storage_source_id=source["storage_source_id"])

    poll_registered_storage_sources(database_url=database_url, now=now, poll_mode="full")
    second_photo.unlink()

    later = now.replace(hour=15)
    poll_registered_storage_sources(database_url=database_url, now=later)

    with engine.connect() as connection:
        row = connection.execute(
            select(photo_files.c.lifecycle_state).where(
                photo_files.c.watched_folder_id == watched_folder["watched_folder_id"],
                photo_files.c.relative_path == "photo_001.jpg",
            )
        ).scalar_one()
    assert row == "active"
```

```python
def test_ingest_facade_poll_registered_storage_sources_delegates_default_incremental_mode(
    monkeypatch,
):
    import app.processing.ingest as isolated_ingest_module

    fake_module = types.ModuleType("app.processing.ingest_polling")
    captured: dict[str, object] = {}

    def fake_poll_registered_storage_sources(
        database_url=None,
        *,
        now=None,
        missing_file_grace_period_days=None,
        poll_chunk_size=100,
        poll_mode="incremental",
    ):
        captured["poll_mode"] = poll_mode
        return IngestResult()

    fake_module.poll_registered_storage_sources = fake_poll_registered_storage_sources
    monkeypatch.setitem(sys.modules, "app.processing.ingest_polling", fake_module)

    isolated_ingest_module.poll_registered_storage_sources(database_url="sqlite:///tmp.db")

    assert captured["poll_mode"] == "incremental"
```

- [ ] **Step 2: Run the default-mode regression test slice to verify it fails only where expected**

Run: `uv run python -m pytest apps/api/tests/test_ingest_polling.py -k "defaults_to_incremental_mode" -q`

Expected: FAIL until the poller default is explicitly set to `incremental`.

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k "delegates_default_incremental_mode" -q`

Expected: FAIL if the facade does not expose the new keyword in a compatible way.

- [ ] **Step 3: Implement any compatibility updates required by the tests**

```python
def poll_registered_storage_sources(
    database_url: str | Path | None = None,
    *,
    now: datetime | None = None,
    missing_file_grace_period_days: int | None = None,
    poll_chunk_size: int = 100,
    poll_mode: PollMode = "incremental",
) -> IngestResult:
    from app.processing.ingest_polling import poll_registered_storage_sources as impl

    return impl(
        database_url=database_url,
        now=now,
        missing_file_grace_period_days=missing_file_grace_period_days,
        poll_chunk_size=poll_chunk_size,
        poll_mode=poll_mode,
    )
```

- [ ] **Step 4: Run the polling regression suite**

Run: `uv run python -m pytest apps/api/tests/test_ingest_polling.py -q`

Expected: PASS

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k "poll_registered_storage_sources" -q`

Expected: PASS

- [ ] **Step 5: Commit the regression and compatibility updates**

```bash
git add apps/api/app/processing/ingest.py apps/api/app/processing/ingest_polling.py apps/api/tests/test_ingest.py apps/api/tests/test_ingest_polling.py
git commit -m "test: lock default incremental polling behavior"
```

### Task 4: Update Operator-Facing Documentation

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: Write the documentation changes**

```md
- `POST /api/v1/internal/storage-sources/poll` defaults to `poll_mode="incremental"` so routine worker polls focus on discovery and queueing of new or changed files.
- Use `poll_mode="full"` when you need missing-file reconciliation and deleted-path lifecycle updates.
```

```md
curl -sS -X POST http://127.0.0.1:<api-port>/api/v1/internal/storage-sources/poll \
  -H 'Content-Type: application/json' \
  -H 'X-Worker-Role: ingest-processor' \
  -d '{"queue_process_limit":100,"poll_mode":"incremental"}'
```

- [ ] **Step 2: Review the docs diff for consistency with the spec**

Run: `git diff -- README.md CONTRIBUTING.md`

Expected: the docs describe incremental as the default routine path and full mode as the explicit deletion-reconciliation path.

- [ ] **Step 3: Commit the docs update**

```bash
git add README.md CONTRIBUTING.md
git commit -m "docs: describe incremental storage polling"
```

### Task 5: Full Verification

**Files:**
- Modify: none
- Test: `apps/api/tests/test_ingest_queue_api.py`
- Test: `apps/api/tests/test_storage_source_polling_service.py`
- Test: `apps/api/tests/test_ingest_polling.py`
- Test: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Run the targeted verification commands**

Run: `uv run python -m pytest apps/api/tests/test_storage_source_polling_service.py -q`

Expected: PASS

Run: `uv run python -m pytest apps/api/tests/test_ingest_queue_api.py -k "poll_storage_sources_endpoint" -q`

Expected: PASS

Run: `uv run python -m pytest apps/api/tests/test_ingest_polling.py -q`

Expected: PASS

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k "poll_registered_storage_sources" -q`

Expected: PASS

- [ ] **Step 2: Inspect the final diff**

Run: `git diff --stat HEAD~4..HEAD`

Expected: only the polling contract, poller behavior, tests, and documentation touched by this plan are included.

- [ ] **Step 3: Create the final implementation commit if any verification fixups were needed**

```bash
git add apps/api/app/processing/ingest.py apps/api/app/processing/ingest_polling.py apps/api/app/routers/ingest_queue.py apps/api/app/services/storage_source_polling.py apps/api/tests/test_ingest.py apps/api/tests/test_ingest_polling.py apps/api/tests/test_ingest_queue_api.py apps/api/tests/test_storage_source_polling_service.py README.md CONTRIBUTING.md
git commit -m "feat: default storage polling to incremental mode"
```
