from app.db.queue import IngestQueueStore
from app.migrations import upgrade_database


def test_enqueue_submission_stores_pending_queue_row(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-store.db'}"
    upgrade_database(database_url)

    store = IngestQueueStore(database_url)

    queue_id = store.enqueue(
        payload_type="photo_metadata",
        payload={"path": "a.heic"},
        idempotency_key="k1",
    )

    rows = store.list_pending()

    assert [row.ingest_queue_id for row in rows] == [queue_id]


def test_enqueue_submission_is_idempotent_for_duplicate_key(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-store-idempotent.db'}"
    upgrade_database(database_url)

    store = IngestQueueStore(database_url)

    first_id = store.enqueue(
        payload_type="photo_metadata",
        payload={"path": "a.heic"},
        idempotency_key="dup-key",
    )
    second_id = store.enqueue(
        payload_type="photo_metadata",
        payload={"path": "b.heic"},
        idempotency_key="dup-key",
    )

    assert second_id == first_id
