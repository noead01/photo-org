from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from app.db.queue import PROCESSING_LEASE_SECONDS
from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import ingest_queue, ingest_runs


def test_operational_activity_api_returns_empty_sections_when_no_current_work(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'operational-activity-idle.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    client = TestClient(app)

    response = client.get("/api/v1/operations/activity")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"observed_at", "polling", "ingest_queue"}
    assert payload["polling"]["items"] == []
    assert payload["polling"]["summary"]["active_count"] == 0
    assert payload["ingest_queue"]["items"] == []
    assert payload["ingest_queue"]["summary"]["processing_count"] == 0
    assert "state" not in payload
    assert "signals" not in payload
    assert "recent_failures" not in payload


def test_operational_activity_api_returns_only_active_polling_work(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'operational-activity-polling.db'}"
    source, watched_folder = _seed_source_with_watched_folder(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        database_name="operational-activity-polling.db",
        database_url=database_url,
    )
    now = datetime(2026, 4, 4, 15, 30, tzinfo=UTC)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(ingest_runs).values(
                ingest_run_id="run-polling",
                watched_folder_id=watched_folder["watched_folder_id"],
                status="processing",
                started_ts=now,
                completed_ts=None,
                files_seen=42,
                files_created=10,
                files_updated=3,
                files_missing=0,
                error_count=0,
                error_summary=None,
            )
        )

    client = TestClient(app)

    response = client.get("/api/v1/operations/activity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["polling"]["summary"]["active_count"] == 1
    assert payload["polling"]["items"][0]["ingest_run_id"] == "run-polling"
    assert payload["ingest_queue"]["items"] == []


def test_operational_activity_api_excludes_completed_and_failed_work_from_live_snapshot(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'operational-activity-history-only.db'}"
    _, watched_folder = _seed_source_with_watched_folder(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        database_name="operational-activity-history-only.db",
        database_url=database_url,
    )
    now = datetime.now(tz=UTC)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(ingest_runs).values(
                ingest_run_id="run-completed",
                watched_folder_id=watched_folder["watched_folder_id"],
                status="completed",
                started_ts=now - timedelta(minutes=3),
                completed_ts=now - timedelta(minutes=2),
                files_seen=12,
                files_created=4,
                files_updated=1,
                files_missing=0,
                error_count=0,
                error_summary=None,
            )
        )
        connection.execute(
            insert(ingest_runs).values(
                ingest_run_id="run-failed",
                watched_folder_id=watched_folder["watched_folder_id"],
                status="failed",
                started_ts=now - timedelta(minutes=2),
                completed_ts=now - timedelta(minutes=1),
                files_seen=8,
                files_created=2,
                files_updated=0,
                files_missing=1,
                error_count=1,
                error_summary="marker mismatch on alias //nas/family-share",
            )
        )
        connection.execute(
            insert(ingest_queue).values(
                ingest_queue_id="queue-completed",
                payload_type="photo_metadata",
                payload_json={"path": "queued/completed.jpg"},
                idempotency_key="completed.jpg",
                status="completed",
                attempt_count=1,
                enqueued_ts=now - timedelta(minutes=10),
                last_attempt_ts=now - timedelta(minutes=5),
                processed_ts=now - timedelta(minutes=4),
                last_error=None,
            )
        )
        connection.execute(
            insert(ingest_queue).values(
                ingest_queue_id="queue-failed",
                payload_type="photo_metadata",
                payload_json={"path": "queued/failed.jpg"},
                idempotency_key="failed.jpg",
                status="failed",
                attempt_count=2,
                enqueued_ts=now - timedelta(minutes=9),
                last_attempt_ts=now - timedelta(minutes=3),
                processed_ts=None,
                last_error="temporary timeout",
            )
        )

    client = TestClient(app)

    response = client.get("/api/v1/operations/activity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["polling"]["items"] == []
    assert payload["ingest_queue"]["items"] == []


def test_operational_activity_api_returns_active_queue_work_with_summary(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'operational-activity-queue.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    now = datetime.now(tz=UTC)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(ingest_queue).values(
                ingest_queue_id="queue-processing",
                payload_type="photo_metadata",
                payload_json={"path": "queued/active.jpg"},
                idempotency_key="active.jpg",
                status="processing",
                attempt_count=1,
                enqueued_ts=now - timedelta(minutes=2),
                last_attempt_ts=now - timedelta(seconds=30),
                processed_ts=None,
                last_error=None,
            )
        )
        connection.execute(
            insert(ingest_queue).values(
                ingest_queue_id="queue-pending",
                payload_type="photo_metadata",
                payload_json={"path": "queued/pending.jpg"},
                idempotency_key="pending.jpg",
                status="pending",
                attempt_count=0,
                enqueued_ts=now - timedelta(minutes=5),
                last_attempt_ts=None,
                processed_ts=None,
                last_error=None,
            )
        )

    client = TestClient(app)

    response = client.get("/api/v1/operations/activity")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"observed_at", "polling", "ingest_queue"}
    assert payload["polling"]["items"] == []
    assert payload["polling"]["summary"]["active_count"] == 0
    assert payload["ingest_queue"]["summary"]["pending_count"] == 1
    assert payload["ingest_queue"]["summary"]["processing_count"] == 1
    assert payload["ingest_queue"]["summary"]["stalled_count"] == 0
    assert payload["ingest_queue"]["summary"]["processed_count"] is None
    assert payload["ingest_queue"]["summary"]["estimated_total"] is None
    assert payload["ingest_queue"]["summary"]["percent_complete"] is None
    assert payload["ingest_queue"]["items"][0]["ingest_queue_id"] == "queue-processing"
    assert payload["ingest_queue"]["items"][0]["payload_type"] == "photo_metadata"
    assert payload["ingest_queue"]["items"][0]["path"] == "queued/active.jpg"
    assert payload["ingest_queue"]["items"][0]["last_attempt_ts"] is not None
    assert payload["ingest_queue"]["items"][0]["is_stalled"] is False
    assert payload["ingest_queue"]["items"][0]["processed_count"] is None
    assert payload["ingest_queue"]["items"][0]["estimated_total"] is None
    assert payload["ingest_queue"]["items"][0]["percent_complete"] is None


def test_operational_activity_api_keeps_unresolved_stalled_queue_work_visible(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'operational-activity-stalled.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    now = datetime.now(tz=UTC)
    stale_attempt_ts = now - timedelta(seconds=PROCESSING_LEASE_SECONDS + 60)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(ingest_queue).values(
                ingest_queue_id="queue-stalled",
                payload_type="photo_metadata",
                payload_json={"path": "queued/stalled.jpg"},
                idempotency_key="stalled.jpg",
                status="processing",
                attempt_count=2,
                enqueued_ts=now - timedelta(minutes=8),
                last_attempt_ts=stale_attempt_ts,
                processed_ts=None,
                last_error="temporary timeout",
            )
        )

    client = TestClient(app)

    response = client.get("/api/v1/operations/activity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["polling"]["items"] == []
    assert payload["ingest_queue"]["summary"]["pending_count"] == 0
    assert payload["ingest_queue"]["summary"]["processing_count"] == 0
    assert payload["ingest_queue"]["summary"]["stalled_count"] == 1
    assert payload["ingest_queue"]["summary"]["processed_count"] is None
    assert payload["ingest_queue"]["summary"]["estimated_total"] is None
    assert payload["ingest_queue"]["summary"]["percent_complete"] is None
    assert payload["ingest_queue"]["items"][0]["ingest_queue_id"] == "queue-stalled"
    assert payload["ingest_queue"]["items"][0]["is_stalled"] is True


def test_operational_activity_history_returns_completed_and_failed_polling_entries_newest_first(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'operational-activity-history-ordering.db'}"
    _, watched_folder = _seed_source_with_watched_folder(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        database_name="operational-activity-history-ordering.db",
        database_url=database_url,
    )
    now = datetime(2026, 4, 4, 17, 0, tzinfo=UTC)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(ingest_runs).values(
                ingest_run_id="run-history-failed",
                watched_folder_id=watched_folder["watched_folder_id"],
                status="failed",
                started_ts=now - timedelta(minutes=10),
                completed_ts=now - timedelta(minutes=9),
                files_seen=12,
                files_created=4,
                files_updated=0,
                files_missing=1,
                error_count=1,
                error_summary="marker mismatch on alias //nas/family-share",
            )
        )
        connection.execute(
            insert(ingest_runs).values(
                ingest_run_id="run-history-completed",
                watched_folder_id=watched_folder["watched_folder_id"],
                status="completed",
                started_ts=now - timedelta(minutes=5),
                completed_ts=now - timedelta(minutes=4),
                files_seen=14,
                files_created=5,
                files_updated=1,
                files_missing=0,
                error_count=0,
                error_summary=None,
            )
        )

    client = TestClient(app)

    response = client.get("/api/v1/operations/activity/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["polling"]["items"][0]["event_type"] == "poll_completed"
    assert payload["polling"]["items"][1]["event_type"] == "poll_failed"
    assert payload["polling"]["items"][0]["watched_folder_id"] == watched_folder["watched_folder_id"]
    assert payload["polling"]["has_more"] is False


def test_operational_activity_history_keeps_polling_and_queue_pagination_separate(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'operational-activity-history-pagination.db'}"
    _, watched_folder = _seed_source_with_watched_folder(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        database_name="operational-activity-history-pagination.db",
        database_url=database_url,
    )
    now = datetime(2026, 4, 4, 18, 0, tzinfo=UTC)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(ingest_runs),
            [
                {
                    "ingest_run_id": "run-history-1",
                    "watched_folder_id": watched_folder["watched_folder_id"],
                    "status": "completed",
                    "started_ts": now - timedelta(minutes=6),
                    "completed_ts": now - timedelta(minutes=5),
                    "files_seen": 10,
                    "files_created": 4,
                    "files_updated": 0,
                    "files_missing": 0,
                    "error_count": 0,
                    "error_summary": None,
                },
                {
                    "ingest_run_id": "run-history-2",
                    "watched_folder_id": watched_folder["watched_folder_id"],
                    "status": "failed",
                    "started_ts": now - timedelta(minutes=4),
                    "completed_ts": now - timedelta(minutes=3),
                    "files_seen": 9,
                    "files_created": 3,
                    "files_updated": 1,
                    "files_missing": 1,
                    "error_count": 1,
                    "error_summary": "transient marker read failure",
                },
            ],
        )
        connection.execute(
            insert(ingest_queue),
            [
                {
                    "ingest_queue_id": "queue-history-1",
                    "payload_type": "photo_metadata",
                    "payload_json": {"path": "queued/history-1.jpg"},
                    "idempotency_key": "history-1.jpg",
                    "status": "completed",
                    "attempt_count": 1,
                    "enqueued_ts": now - timedelta(minutes=9),
                    "last_attempt_ts": now - timedelta(minutes=8),
                    "processed_ts": now - timedelta(minutes=7),
                    "last_error": None,
                },
                {
                    "ingest_queue_id": "queue-history-2",
                    "payload_type": "photo_metadata",
                    "payload_json": {"path": "queued/history-2.jpg"},
                    "idempotency_key": "history-2.jpg",
                    "status": "failed",
                    "attempt_count": 2,
                    "enqueued_ts": now - timedelta(minutes=5),
                    "last_attempt_ts": now - timedelta(minutes=4),
                    "processed_ts": None,
                    "last_error": "temporary timeout",
                },
            ],
        )

    client = TestClient(app)

    response = client.get(
        "/api/v1/operations/activity/history",
        params={"polling_limit": 1, "queue_limit": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["polling"]["items"]) == 1
    assert len(payload["ingest_queue"]["items"]) == 1
    assert payload["polling"]["next_cursor"] is not None
    assert payload["ingest_queue"]["next_cursor"] is not None


def test_operational_activity_history_rejects_malformed_cursor_with_client_error(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'operational-activity-history-bad-cursor.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    client = TestClient(app)

    response = client.get(
        "/api/v1/operations/activity/history",
        params={"polling_cursor": "not-a-valid-cursor"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid polling_cursor"}


def _seed_source_with_watched_folder(*, tmp_path, monkeypatch, database_name: str, database_url: str):
    from app.services.storage_sources import attach_storage_source_alias, create_storage_source
    from app.services.watched_folders import create_watched_folder

    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    root = tmp_path / "family-share"
    watched_root = root / "2024" / "trips"
    watched_root.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 4, 4, 14, 0, tzinfo=UTC)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family Share",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=str(root),
            now=now,
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=str(root),
            watched_path=str(watched_root),
            display_name="Trips",
            now=now,
        )

    return source, watched_folder
