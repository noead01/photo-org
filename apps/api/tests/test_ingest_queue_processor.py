from sqlalchemy import create_engine, select, update
from sqlalchemy.engine import Connection

from app.db.queue import IngestQueueStore
from app.migrations import upgrade_database
from app.services import ingest_queue_processor
from app.services.ingest_queue_processor import process_pending_ingest_queue
from app.storage import photos
from photoorg_db_schema import ingest_queue


SAMPLE_PAYLOAD = {
    "photo_id": "photo-1",
    "path": "queued/photo-1.heic",
    "sha256": "a" * 64,
    "filesize": 123,
    "ext": "heic",
    "created_ts": "2024-01-01T00:00:00+00:00",
    "modified_ts": "2024-01-02T00:00:00+00:00",
    "shot_ts": None,
    "shot_ts_source": None,
    "camera_make": None,
    "camera_model": None,
    "software": None,
    "orientation": None,
    "gps_latitude": None,
    "gps_longitude": None,
    "gps_altitude": None,
    "faces_count": 0,
}


def load_photo_paths(database_url: str) -> list[str]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        rows = connection.execute(select(photos.c.path).order_by(photos.c.path)).all()
    return [row[0] for row in rows]


def test_process_pending_rows_applies_domain_write_and_marks_queue_complete(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-1",
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    assert result.processed == 1
    assert load_photo_paths(database_url) == [SAMPLE_PAYLOAD["path"]]
    assert queue_store.list_by_status("completed")


def test_process_pending_rows_is_idempotent_for_repeated_trigger_calls(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-idempotent.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-1",
    )

    first = process_pending_ingest_queue(database_url, limit=10)
    second = process_pending_ingest_queue(database_url, limit=10)

    assert first.processed == 1
    assert second.processed == 0


def test_process_pending_rows_marks_unsupported_payload_failed_without_stranding(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-unsupported.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="unknown_payload",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="bad-payload",
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    assert result.processed == 0
    assert result.failed == 1
    assert load_photo_paths(database_url) == []
    assert queue_store.list_by_status("processing") == []
    failed_rows = queue_store.list_by_status("failed")
    assert len(failed_rows) == 1
    assert failed_rows[0].attempt_count == 1
    assert "Unsupported payload_type" in failed_rows[0].last_error


def test_process_pending_rows_keeps_transient_domain_write_failures_retryable(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-transient.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-transient",
    )

    original_upsert = ingest_queue_processor.upsert_photo

    def flaky_upsert(*args, **kwargs):
        raise RuntimeError("transient db outage")

    monkeypatch.setattr(ingest_queue_processor, "upsert_photo", flaky_upsert)

    first = process_pending_ingest_queue(database_url, limit=10)
    assert first.processed == 0
    assert first.failed == 0
    assert queue_store.list_by_status("failed") == []
    pending_rows = queue_store.list_by_status("pending")
    assert len(pending_rows) == 1
    assert pending_rows[0].attempt_count == 0

    monkeypatch.setattr(ingest_queue_processor, "upsert_photo", original_upsert)

    second = process_pending_ingest_queue(database_url, limit=10)

    assert second.processed == 1
    assert second.failed == 0


def test_process_pending_rows_retries_rows_left_in_processing(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-reclaim.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)
    queue_id = queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-reclaim",
    )

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == queue_id)
            .values(status="processing")
        )

    result = process_pending_ingest_queue(database_url, limit=10)

    assert result.processed == 1
    assert result.failed == 0
    assert load_photo_paths(database_url) == [SAMPLE_PAYLOAD["path"]]
    assert queue_store.list_by_status("processing") == []
    assert len(queue_store.list_by_status("completed")) == 1


def test_process_pending_rows_keeps_row_retryable_when_completion_transition_fails(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-completion-failure.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-completion-failure",
    )

    original_execute = Connection.execute

    def flaky_execute(self, statement, *args, **kwargs):
        values = getattr(statement, "_values", {})
        if getattr(statement, "table", None) is ingest_queue and any(
            (getattr(column, "name", column) == "status")
            and getattr(value, "value", value) == "completed"
            for column, value in values.items()
        ):
            raise RuntimeError("queue completion update failed")
        return original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Connection, "execute", flaky_execute)

    first = process_pending_ingest_queue(database_url, limit=10)

    monkeypatch.setattr(Connection, "execute", original_execute)

    second = process_pending_ingest_queue(database_url, limit=10)

    assert first.processed == 0
    assert first.failed == 0
    assert second.processed == 1
    assert second.failed == 0
    assert load_photo_paths(database_url) == [SAMPLE_PAYLOAD["path"]]
    assert queue_store.list_by_status("failed") == []
    assert queue_store.list_by_status("processing") == []
    assert len(queue_store.list_by_status("completed")) == 1
