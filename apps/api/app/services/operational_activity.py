from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from app.db.queue import PROCESSING_LEASE_SECONDS, _processing_lease_cutoff
from app.storage import ingest_queue, ingest_runs, watched_folders


def get_operational_activity(
    connection: Connection,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_at = _normalize_timestamp(now or datetime.now(tz=UTC))
    lease_cutoff = _processing_lease_cutoff(observed_at)
    active_polling = _list_active_polling(connection)
    queue_status = _load_ingest_queue_status(connection, lease_cutoff=lease_cutoff)
    recent_failures = _list_recent_failures(connection)
    signals = {
        "recent_failure_count": len(recent_failures),
        "stalled_count": queue_status["stalled_count"],
    }

    return {
        "state": _derive_activity_state(
            active_polling_count=len(active_polling),
            processing_queue_count=queue_status["processing_count"],
            signal_counts=signals,
        ),
        "observed_at": _iso_utc(observed_at),
        "polling": {
            "active_count": len(active_polling),
            "active_watched_folders": active_polling,
        },
        "ingest_queue": queue_status,
        "signals": signals,
        "recent_failures": recent_failures,
    }


def _list_active_polling(connection: Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(
            ingest_runs.c.watched_folder_id,
            watched_folders.c.storage_source_id,
            watched_folders.c.display_name,
            watched_folders.c.scan_path,
            ingest_runs.c.started_ts,
        )
        .select_from(
            ingest_runs.join(
                watched_folders,
                ingest_runs.c.watched_folder_id == watched_folders.c.watched_folder_id,
            )
        )
        .where(ingest_runs.c.status == "processing")
        .where(ingest_runs.c.watched_folder_id.is_not(None))
        .order_by(ingest_runs.c.started_ts.desc(), ingest_runs.c.ingest_run_id.desc())
    ).mappings()
    return [
        {
            "watched_folder_id": str(row["watched_folder_id"]),
            "storage_source_id": str(row["storage_source_id"]),
            "display_name": row["display_name"],
            "scan_path": str(row["scan_path"]),
            "started_ts": _iso_utc(row["started_ts"]),
        }
        for row in rows
    ]


def _load_ingest_queue_status(
    connection: Connection,
    *,
    lease_cutoff: datetime,
) -> dict[str, Any]:
    pending_count = _count_rows(connection, ingest_queue.c.status == "pending")
    processing_count = _count_rows(
        connection,
        (ingest_queue.c.status == "processing")
        & ingest_queue.c.last_attempt_ts.is_not(None)
        & (ingest_queue.c.last_attempt_ts > lease_cutoff),
    )
    stalled_count = _count_rows(
        connection,
        (ingest_queue.c.status == "processing")
        & (
            ingest_queue.c.last_attempt_ts.is_(None)
            | (ingest_queue.c.last_attempt_ts <= lease_cutoff)
        ),
    )
    failed_count = _count_rows(connection, ingest_queue.c.status == "failed")
    oldest_pending_ts = connection.execute(
        select(func.min(ingest_queue.c.enqueued_ts)).where(ingest_queue.c.status == "pending")
    ).scalar_one()
    return {
        "pending_count": pending_count,
        "processing_count": processing_count,
        "failed_count": failed_count,
        "stalled_count": stalled_count,
        "lease_timeout_seconds": PROCESSING_LEASE_SECONDS,
        "oldest_pending_ts": _iso_utc(oldest_pending_ts),
    }


def _count_rows(connection: Connection, criterion) -> int:
    return int(connection.execute(select(func.count()).select_from(ingest_queue).where(criterion)).scalar_one())


def _list_recent_failures(connection: Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(
            ingest_runs.c.watched_folder_id,
            watched_folders.c.display_name,
            ingest_runs.c.status,
            ingest_runs.c.error_summary,
            ingest_runs.c.completed_ts,
        )
        .select_from(
            ingest_runs.join(
                watched_folders,
                ingest_runs.c.watched_folder_id == watched_folders.c.watched_folder_id,
            )
        )
        .where(ingest_runs.c.error_count > 0)
        .order_by(
            ingest_runs.c.completed_ts.desc().nullslast(),
            ingest_runs.c.started_ts.desc(),
            ingest_runs.c.ingest_run_id.desc(),
        )
        .limit(5)
    ).mappings()
    return [
        {
            "kind": "watched_folder_ingest",
            "watched_folder_id": str(row["watched_folder_id"]),
            "display_name": row["display_name"],
            "status": str(row["status"]),
            "error_summary": row["error_summary"],
            "completed_ts": _iso_utc(row["completed_ts"]),
        }
        for row in rows
    ]


def _derive_activity_state(
    *,
    active_polling_count: int,
    processing_queue_count: int,
    signal_counts: dict[str, int],
) -> str:
    if active_polling_count > 0:
        return "polling"
    if processing_queue_count > 0:
        return "processing_queue"
    if signal_counts["recent_failure_count"] > 0 or signal_counts["stalled_count"] > 0:
        return "attention_required"
    return "idle"


def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso_utc(value: datetime | None) -> str | None:
    normalized = _normalize_timestamp(value)
    if normalized is None:
        return None
    return normalized.isoformat().replace("+00:00", "Z")
