from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.exc import IntegrityError

from app.db.queue import IngestQueueStore
from app.migrations import upgrade_database
from photoorg_db_schema import ingest_queue


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
    assert rows[0].payload_type == "photo_metadata"
    assert rows[0].payload_json == {"path": "a.heic"}
    assert rows[0].status == "pending"
    assert rows[0].attempt_count == 0


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
    rows = store.list_pending()

    assert [row.ingest_queue_id for row in rows] == [first_id]
    assert rows[0].payload_type == "photo_metadata"
    assert rows[0].payload_json == {"path": "a.heic"}
    assert rows[0].status == "pending"
    assert rows[0].attempt_count == 0


def test_enqueue_reraises_non_idempotency_integrity_errors(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-store-integrity.db'}"
    upgrade_database(database_url)

    store = IngestQueueStore(database_url)

    with pytest.raises(IntegrityError):
        store.enqueue(
            payload_type=None,
            payload={"path": "a.heic"},
            idempotency_key="bad-null-payload-type",
        )


def test_enqueue_reraises_invalid_submission_for_existing_idempotency_key(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-store-mixed-failure.db'}"
    upgrade_database(database_url)

    store = IngestQueueStore(database_url)
    queue_id = store.enqueue(
        payload_type="photo_metadata",
        payload={"path": "a.heic"},
        idempotency_key="dup-key",
    )

    with pytest.raises(IntegrityError):
        store.enqueue(
            payload_type=None,
            payload={"path": "b.heic"},
            idempotency_key="dup-key",
        )

    rows = store.list_pending()

    assert [row.ingest_queue_id for row in rows] == [queue_id]
    assert rows[0].payload_type == "photo_metadata"
    assert rows[0].payload_json == {"path": "a.heic"}


def test_list_processable_prioritizes_extracted_payloads_over_candidates(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-store-priority.db'}"
    upgrade_database(database_url)

    store = IngestQueueStore(database_url)

    candidate_id = store.enqueue(
        payload_type="ingest_candidate",
        payload={"path": "candidate.jpg"},
        idempotency_key="candidate-key",
    )
    extracted_id = store.enqueue(
        payload_type="extracted_photo",
        payload={"path": "extracted.jpg"},
        idempotency_key="extracted-key",
    )
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        base_time = datetime(2024, 1, 1, tzinfo=UTC)
        connection.execute(
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == candidate_id)
            .values(enqueued_ts=base_time)
        )
        connection.execute(
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == extracted_id)
            .values(enqueued_ts=base_time + timedelta(seconds=1))
        )

    processable_rows = store.list_processable(limit=1)

    assert len(processable_rows) == 1
    assert processable_rows[0].ingest_queue_id == extracted_id
    assert processable_rows[0].payload_type == "extracted_photo"
    assert processable_rows[0].ingest_queue_id != candidate_id


def test_refresh_nonprocessing_in_transaction_replaces_payload_for_completed_row(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-store-refresh-nonprocessing.db'}"
    upgrade_database(database_url)
    store = IngestQueueStore(database_url)

    queue_id = store.enqueue(
        payload_type="face_suggestion_recompute",
        payload={"person_id": "person-1", "debounce_until_ts": "2026-05-03T12:00:00+00:00"},
        idempotency_key="face_suggestion_recompute:person-1",
    )
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == queue_id)
            .values(status="completed")
        )
        refreshed = store.refresh_nonprocessing_in_transaction(
            queue_id,
            payload={"person_id": "person-1", "debounce_until_ts": "2026-05-03T12:00:05+00:00"},
            connection=connection,
        )
        row = store.get_row_in_transaction(queue_id, connection=connection)

    assert refreshed is True
    assert row is not None
    assert row.status == "pending"
    assert row.payload_json["debounce_until_ts"] == "2026-05-03T12:00:05+00:00"
