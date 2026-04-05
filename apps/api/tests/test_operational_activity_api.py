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
    assert payload["polling"]["items"] == [
        {
            "ingest_run_id": "run-polling",
            "watched_folder_id": watched_folder["watched_folder_id"],
            "storage_source_id": source["storage_source_id"],
            "display_name": "Trips",
            "scan_path": str(tmp_path / "family-share" / "2024" / "trips"),
            "started_ts": "2026-04-04T15:30:00Z",
        }
    ]


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


def test_operational_activity_api_reports_active_queue_processing(tmp_path, monkeypatch):
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
    assert payload["state"] == "processing_queue"
    assert payload["polling"]["active_count"] == 0
    assert payload["ingest_queue"]["pending_count"] == 1
    assert payload["ingest_queue"]["processing_count"] == 1
    assert payload["ingest_queue"]["failed_count"] == 0
    assert payload["ingest_queue"]["stalled_count"] == 0
    assert payload["ingest_queue"]["oldest_pending_ts"] == (
        now - timedelta(minutes=5)
    ).isoformat().replace("+00:00", "Z")


def test_operational_activity_api_reports_attention_required_for_failed_or_stalled_work(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'operational-activity-attention.db'}"
    _, watched_folder = _seed_source_with_watched_folder(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        database_name="operational-activity-attention.db",
        database_url=database_url,
    )
    now = datetime.now(tz=UTC)
    stale_attempt_ts = now - timedelta(seconds=PROCESSING_LEASE_SECONDS + 60)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(ingest_runs).values(
                ingest_run_id="run-failed",
                watched_folder_id=watched_folder["watched_folder_id"],
                status="failed",
                started_ts=now - timedelta(minutes=2),
                completed_ts=now - timedelta(minutes=1),
                files_seen=12,
                files_created=2,
                files_updated=1,
                files_missing=0,
                error_count=1,
                error_summary="marker mismatch on alias //nas/family-share",
            )
        )
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
    assert payload["state"] == "attention_required"
    assert payload["signals"]["recent_failure_count"] == 1
    assert payload["signals"]["stalled_count"] == 1
    assert payload["ingest_queue"]["stalled_count"] == 1
    assert payload["recent_failures"][0]["kind"] == "watched_folder_ingest"
    assert payload["recent_failures"][0]["watched_folder_id"] == watched_folder["watched_folder_id"]
    assert payload["recent_failures"][0]["error_summary"] == "marker mismatch on alias //nas/family-share"


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
