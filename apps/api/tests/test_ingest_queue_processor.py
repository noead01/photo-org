from sqlalchemy import create_engine, select

from app.db.queue import IngestQueueStore
from app.migrations import upgrade_database
from app.services.ingest_queue_processor import process_pending_ingest_queue
from app.storage import photos


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
