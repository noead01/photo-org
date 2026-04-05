from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from app.db.queue import _processing_lease_cutoff
from app.storage import ingest_queue, ingest_runs, watched_folders


def get_operational_activity(
    connection: Connection,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_at = _normalize_timestamp(now or datetime.now(tz=UTC))
    lease_cutoff = _processing_lease_cutoff(observed_at)
    polling_items = _list_active_polling(connection)
    queue_section = _load_live_ingest_queue(connection, lease_cutoff=lease_cutoff)
    return {
        "observed_at": _iso_utc(observed_at),
        "polling": {
            "items": polling_items,
            "summary": _build_polling_live_summary(polling_items),
        },
        "ingest_queue": queue_section,
    }


def _list_active_polling(connection: Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(
            ingest_runs.c.ingest_run_id,
            ingest_runs.c.watched_folder_id,
            watched_folders.c.storage_source_id,
            watched_folders.c.display_name,
            watched_folders.c.scan_path,
            ingest_runs.c.started_ts,
            ingest_runs.c.files_seen,
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
            "ingest_run_id": str(row["ingest_run_id"]),
            "watched_folder_id": str(row["watched_folder_id"]),
            "storage_source_id": str(row["storage_source_id"]),
            "display_name": row["display_name"],
            "scan_path": str(row["scan_path"]),
            "started_ts": _iso_utc(row["started_ts"]),
            "files_seen": row["files_seen"],
            "estimated_files_total": None,
            "percent_complete": None,
        }
        for row in rows
    ]


def _build_polling_live_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    files_seen_values = [item["files_seen"] for item in items if item["files_seen"] is not None]
    return {
        "active_count": len(items),
        "files_seen": sum(files_seen_values) if files_seen_values else 0,
        "estimated_files_total": None,
        "percent_complete": None,
    }


def _load_live_ingest_queue(
    connection: Connection,
    *,
    lease_cutoff: datetime,
) -> dict[str, Any]:
    pending_count = _count_rows(connection, ingest_queue.c.status == "pending")
    rows = connection.execute(
        select(
            ingest_queue.c.ingest_queue_id,
            ingest_queue.c.payload_type,
            ingest_queue.c.payload_json,
            ingest_queue.c.last_attempt_ts,
        )
        .where(ingest_queue.c.status == "processing")
        .order_by(
            ingest_queue.c.last_attempt_ts.desc().nullslast(),
            ingest_queue.c.enqueued_ts,
            ingest_queue.c.ingest_queue_id,
        )
    ).mappings()

    items = []
    processing_count = 0
    stalled_count = 0
    for row in rows:
        last_attempt_ts = _normalize_timestamp(row["last_attempt_ts"])
        is_stalled = last_attempt_ts is None or last_attempt_ts <= lease_cutoff
        if is_stalled:
            stalled_count += 1
        else:
            processing_count += 1
        items.append(
            {
                "ingest_queue_id": str(row["ingest_queue_id"]),
                "payload_type": row["payload_type"],
                "path": _extract_queue_path(row["payload_json"]),
                "last_attempt_ts": _iso_utc(last_attempt_ts),
                "is_stalled": is_stalled,
                "processed_count": 0,
                "estimated_total": None,
                "percent_complete": None,
            }
        )

    return {
        "items": items,
        "summary": {
            "pending_count": pending_count,
            "processing_count": processing_count,
            "stalled_count": stalled_count,
            "processed_count": 0,
            "estimated_total": None,
            "percent_complete": None,
        },
    }


def _extract_queue_path(payload_json: Any) -> str | None:
    if not isinstance(payload_json, dict):
        return None
    path = payload_json.get("path")
    if path is None:
        return None
    return str(path)


def _count_rows(connection: Connection, criterion) -> int:
    return int(
        connection.execute(select(func.count()).select_from(ingest_queue).where(criterion)).scalar_one()
    )


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
