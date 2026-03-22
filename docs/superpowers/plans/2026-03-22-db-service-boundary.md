# Database Service Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish an API-owned domain persistence boundary where the worker appends ingest submissions to a queue table and triggers API-side processing instead of writing domain tables directly.

**Architecture:** Keep domain-table reads and writes inside the API service, add an internal ingest queue table as infrastructure, and convert the current ingest path into a queue producer plus an API-owned queue processor. The first slice proves one end-to-end flow from worker submission to API-applied domain mutation without implementing the full Phase 1 ingestion system.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, uv workspace, pytest

---

### Task 1: Add the ingest queue schema surface

**Files:**
- Modify: `packages/db-schema/photoorg_db_schema/schema.py`
- Modify: `packages/db-schema/photoorg_db_schema/__init__.py`
- Modify: `apps/api/alembic/versions/20260321_000001_initial_schema.py`
- Test: `apps/api/tests/test_schema_definition.py`
- Test: `apps/api/tests/test_migrations.py`

- [ ] **Step 1: Write the failing schema tests**

```python
def test_schema_metadata_includes_ingest_queue_table():
    assert "ingest_queue" in metadata.tables


def test_upgrade_database_creates_ingest_queue_table(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        tables = set(connection.dialect.get_table_names(connection))
    assert "ingest_queue" in tables
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py -q`
Expected: FAIL because the schema and migration do not define `ingest_queue`.

- [ ] **Step 3: Add the minimal schema and migration support**

```python
ingest_queue = Table(
    "ingest_queue",
    metadata,
    Column("ingest_queue_id", String(36), primary_key=True),
    Column("payload_type", String, nullable=False),
    Column("payload_json", JSON, nullable=False),
    Column("idempotency_key", String, nullable=False, unique=True),
    Column("status", String, nullable=False, server_default=text("'pending'")),
    Column("attempt_count", Integer, nullable=False, server_default=text("0")),
    Column("enqueued_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("last_attempt_ts", TIMESTAMP(timezone=True)),
    Column("processed_ts", TIMESTAMP(timezone=True)),
    Column("last_error", Text),
)
Index("idx_ingest_queue_status_enqueued_ts", ingest_queue.c.status, ingest_queue.c.enqueued_ts)
```

- [ ] **Step 4: Run the schema tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/db-schema/photoorg_db_schema/schema.py packages/db-schema/photoorg_db_schema/__init__.py apps/api/alembic/versions/20260321_000001_initial_schema.py apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py
git commit -m "feat(db): add ingest queue schema"
```

### Task 2: Introduce API-owned database and queue modules

**Files:**
- Create: `apps/api/app/db/__init__.py`
- Create: `apps/api/app/db/config.py`
- Create: `apps/api/app/db/session.py`
- Create: `apps/api/app/db/queue.py`
- Modify: `apps/api/app/storage.py`
- Modify: `apps/api/app/dependencies.py`
- Test: `apps/api/tests/test_queue_store.py`

- [ ] **Step 1: Write the failing queue-store tests**

```python
def test_enqueue_submission_stores_pending_queue_row(tmp_path):
    store = IngestQueueStore(database_url)
    queue_id = store.enqueue(payload_type="photo_metadata", payload={"path": "a.heic"}, idempotency_key="k1")
    rows = store.list_pending()
    assert [row.ingest_queue_id for row in rows] == [queue_id]


def test_enqueue_submission_is_idempotent_for_duplicate_key(tmp_path):
    store = IngestQueueStore(database_url)
    first_id = store.enqueue(..., idempotency_key="dup-key")
    second_id = store.enqueue(..., idempotency_key="dup-key")
    assert second_id == first_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_queue_store.py -q`
Expected: FAIL because the queue store module does not exist.

- [ ] **Step 3: Implement the minimal shared API-owned DB modules**

```python
class IngestQueueStore:
    def __init__(self, database_url: str | Path | None = None) -> None:
        self._session_factory = create_session_factory(database_url)

    def enqueue(self, *, payload_type: str, payload: dict, idempotency_key: str) -> str:
        ...

    def list_pending(self) -> list[QueueRow]:
        ...
```

- [ ] **Step 4: Run the queue-store tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_queue_store.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/db/__init__.py apps/api/app/db/config.py apps/api/app/db/session.py apps/api/app/db/queue.py apps/api/app/storage.py apps/api/app/dependencies.py apps/api/tests/test_queue_store.py
git commit -m "feat(api): add queue-backed db access modules"
```

### Task 3: Add an API-owned queue processor

**Files:**
- Create: `apps/api/app/services/ingest_queue_processor.py`
- Modify: `apps/api/app/db/queue.py`
- Test: `apps/api/tests/test_ingest_queue_processor.py`

- [ ] **Step 1: Write the failing processor tests**

```python
def test_process_pending_rows_applies_domain_write_and_marks_queue_complete(tmp_path):
    queue_store.enqueue(payload_type="photo_metadata", payload=sample_payload, idempotency_key="photo-1")
    result = process_pending_ingest_queue(database_url, limit=10)
    assert result.processed == 1
    assert load_photo_paths(database_url) == [sample_payload["path"]]
    assert queue_store.list_by_status("completed")


def test_process_pending_rows_is_idempotent_for_repeated_trigger_calls(tmp_path):
    queue_store.enqueue(payload_type="photo_metadata", payload=sample_payload, idempotency_key="photo-1")
    first = process_pending_ingest_queue(database_url, limit=10)
    second = process_pending_ingest_queue(database_url, limit=10)
    assert first.processed == 1
    assert second.processed == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_ingest_queue_processor.py -q`
Expected: FAIL because the processor service does not exist.

- [ ] **Step 3: Implement the minimal queue processor**

```python
def process_pending_ingest_queue(database_url: str | Path | None = None, *, limit: int = 100) -> ProcessQueueResult:
    claimed_rows = queue_store.claim_pending(limit=limit)
    for row in claimed_rows:
        try:
            if row.payload_type == "photo_metadata":
                upsert_photo(connection, payload_to_photo_record(row.payload_json))
            queue_store.mark_completed(row.ingest_queue_id)
        except Exception as exc:
            queue_store.mark_failed(row.ingest_queue_id, str(exc))
```

- [ ] **Step 4: Run the processor tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_ingest_queue_processor.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/ingest_queue_processor.py apps/api/app/db/queue.py apps/api/tests/test_ingest_queue_processor.py
git commit -m "feat(api): process queued ingest submissions"
```

### Task 4: Expose the privileged queue-processing API endpoint

**Files:**
- Create: `apps/api/app/routers/ingest_queue.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/dependencies.py`
- Test: `apps/api/tests/test_ingest_queue_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_process_queue_endpoint_rejects_missing_worker_role(client):
    response = client.post("/api/v1/internal/ingest-queue/process")
    assert response.status_code == 403


def test_process_queue_endpoint_processes_pending_rows_for_worker_role(client, queue_store):
    queue_store.enqueue(payload_type="photo_metadata", payload=sample_payload, idempotency_key="photo-1")
    response = client.post(
        "/api/v1/internal/ingest-queue/process",
        headers={"X-Worker-Role": "ingest-processor"},
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_ingest_queue_api.py -q`
Expected: FAIL because the endpoint and authorization dependency do not exist.

- [ ] **Step 3: Implement the endpoint and worker-role guard**

```python
@router.post("/internal/ingest-queue/process")
def process_ingest_queue_endpoint(
    body: ProcessQueueRequest,
    _: None = Depends(require_worker_role),
) -> ProcessQueueResponse:
    result = process_pending_ingest_queue(limit=body.limit)
    return ProcessQueueResponse(processed=result.processed, failed=result.failed)
```

- [ ] **Step 4: Run the API tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_ingest_queue_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/routers/ingest_queue.py apps/api/app/main.py apps/api/app/dependencies.py apps/api/tests/test_ingest_queue_api.py
git commit -m "feat(api): add worker queue processing endpoint"
```

### Task 5: Convert the current ingest CLI path into a queue producer and trigger client

**Files:**
- Modify: `apps/api/app/processing/ingest.py`
- Modify: `apps/api/app/cli.py`
- Create: `apps/api/app/services/worker_queue_trigger.py`
- Test: `apps/api/tests/test_ingest.py`
- Test: `apps/api/tests/test_cli.py`

- [ ] **Step 1: Write the failing worker-path tests**

```python
def test_ingest_directory_enqueues_records_without_writing_photos_table(tmp_path):
    result = ingest_directory(samples_dir, database_url=db_url, queue_commit_chunk_size=1000)
    assert result.enqueued == 10
    assert load_photo_count(db_url) == 0
    assert load_pending_queue_count(db_url) == 10


def test_ingest_cli_triggers_queue_processing_when_chunk_threshold_is_reached(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("app.services.worker_queue_trigger.trigger_queue_processing", lambda **kwargs: calls.append(kwargs))
    exit_code = main(["ingest", str(samples_dir), "--database-url", db_url, "--queue-commit-chunk-size", "2"])
    assert exit_code == 0
    assert calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_ingest.py apps/api/tests/test_cli.py -q`
Expected: FAIL because the ingest flow still writes domain tables directly and no trigger client exists.

- [ ] **Step 3: Implement queue-based ingest submission**

```python
def ingest_directory(..., queue_commit_chunk_size: int = 100, trigger_client: QueueTriggerClient | None = None) -> IngestResult:
    for photo_path in iter_photo_files(source_root):
        payload = build_ingest_submission(photo_path, face_detector=face_detector)
        queue_store.enqueue(payload_type="photo_metadata", payload=payload, idempotency_key=payload["idempotency_key"])
        if pending_since_last_trigger >= queue_commit_chunk_size:
            trigger_client.process_pending_queue()
```

- [ ] **Step 4: Run the ingest and CLI tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_ingest.py apps/api/tests/test_cli.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/processing/ingest.py apps/api/app/cli.py apps/api/app/services/worker_queue_trigger.py apps/api/tests/test_ingest.py apps/api/tests/test_cli.py
git commit -m "feat(worker): enqueue ingest submissions via api-owned boundary"
```

### Task 6: Document the boundary and run the focused validation slice

**Files:**
- Modify: `CONTRIBUTING.md`
- Modify: `README.md`
- Modify: `docs/adr/README.md`
- Test: `apps/api/tests/test_schema_definition.py`
- Test: `apps/api/tests/test_migrations.py`
- Test: `apps/api/tests/test_queue_store.py`
- Test: `apps/api/tests/test_ingest_queue_processor.py`
- Test: `apps/api/tests/test_ingest_queue_api.py`
- Test: `apps/api/tests/test_ingest.py`
- Test: `apps/api/tests/test_cli.py`

- [ ] **Step 1: Write the documentation updates**

```md
## Worker and API persistence boundary

- workers append ingest submissions to the internal queue table
- workers do not mutate domain tables directly
- the API processes queued submissions through the privileged worker endpoint
```

- [ ] **Step 2: Run the focused validation commands**

Run: `uv run pytest apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_queue_store.py apps/api/tests/test_ingest_queue_processor.py apps/api/tests/test_ingest_queue_api.py apps/api/tests/test_ingest.py apps/api/tests/test_cli.py -q`
Expected: PASS

Run: `make lint`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md README.md docs/adr/README.md apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_queue_store.py apps/api/tests/test_ingest_queue_processor.py apps/api/tests/test_ingest_queue_api.py apps/api/tests/test_ingest.py apps/api/tests/test_cli.py
git commit -m "docs: describe api-owned ingest queue boundary"
```
