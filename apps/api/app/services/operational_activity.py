from __future__ import annotations

import base64
import binascii
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.engine import Connection

from app.db.queue import _processing_lease_cutoff
from app.storage import ingest_queue, ingest_runs, watched_folders


class InvalidOperationalActivityCursor(ValueError):
    pass


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


def get_operational_activity_history(
    connection: Connection,
    *,
    polling_limit: int,
    polling_cursor: str | None,
    queue_limit: int,
    queue_cursor: str | None,
) -> dict[str, Any]:
    polling_section = _load_polling_history(
        connection,
        limit=polling_limit,
        cursor=polling_cursor,
    )
    queue_section = _load_queue_history(
        connection,
        limit=queue_limit,
        cursor=queue_cursor,
    )
    return {
        "polling": polling_section,
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
    files_seen = None
    if all(item["files_seen"] is not None for item in items):
        files_seen = sum(int(item["files_seen"]) for item in items)
    return {
        "active_count": len(items),
        "files_seen": files_seen,
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
                "processed_count": None,
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
            "processed_count": None,
            "estimated_total": None,
            "percent_complete": None,
        },
    }


def _load_polling_history(
    connection: Connection,
    *,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    normalized_limit = max(1, limit)
    query = (
        select(
            ingest_runs.c.ingest_run_id,
            ingest_runs.c.watched_folder_id,
            watched_folders.c.display_name,
            ingest_runs.c.status,
            ingest_runs.c.completed_ts,
            ingest_runs.c.started_ts,
            ingest_runs.c.error_summary,
        )
        .select_from(
            ingest_runs.join(
                watched_folders,
                ingest_runs.c.watched_folder_id == watched_folders.c.watched_folder_id,
            )
        )
        .where(ingest_runs.c.status != "processing")
        .where(ingest_runs.c.watched_folder_id.is_not(None))
    )

    cursor_values = _decode_cursor(cursor, parameter_name="polling_cursor")
    if cursor_values is not None:
        query = query.where(_polling_history_after_cursor(cursor_values))

    rows = list(
        connection.execute(
            query.order_by(
                ingest_runs.c.completed_ts.desc().nullslast(),
                ingest_runs.c.started_ts.desc(),
                ingest_runs.c.ingest_run_id.desc(),
            ).limit(normalized_limit + 1)
        ).mappings()
    )

    items = [
        {
            "ingest_run_id": str(row["ingest_run_id"]),
            "watched_folder_id": str(row["watched_folder_id"]),
            "display_name": row["display_name"],
            "event_type": _polling_event_type(row["status"]),
            "event_ts": _iso_utc(row["completed_ts"] or row["started_ts"]),
            "status": row["status"],
            "error_summary": row["error_summary"],
        }
        for row in rows[:normalized_limit]
    ]
    has_more = len(rows) > normalized_limit
    next_cursor = None
    if has_more and items:
        last_row = rows[normalized_limit - 1]
        next_cursor = _encode_cursor(
            completed_ts=_normalize_timestamp(last_row["completed_ts"]),
            started_ts=_normalize_timestamp(last_row["started_ts"]),
            row_id=str(last_row["ingest_run_id"]),
        )

    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


def _load_queue_history(
    connection: Connection,
    *,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    normalized_limit = max(1, limit)
    cursor_values = _decode_cursor(cursor, parameter_name="queue_cursor")
    event_ts = func.coalesce(
        ingest_queue.c.processed_ts,
        ingest_queue.c.last_attempt_ts,
        ingest_queue.c.enqueued_ts,
    )

    query = (
        select(
            ingest_queue.c.ingest_queue_id,
            ingest_queue.c.payload_type,
            ingest_queue.c.payload_json,
            ingest_queue.c.status,
            ingest_queue.c.processed_ts,
            ingest_queue.c.last_attempt_ts,
            ingest_queue.c.enqueued_ts,
            ingest_queue.c.last_error,
            event_ts.label("event_ts"),
        )
        .where(ingest_queue.c.status.in_(("completed", "failed")))
    )
    if cursor_values is not None:
        query = query.where(_queue_history_after_cursor(cursor_values, event_ts))

    rows = list(
        connection.execute(
            query.order_by(event_ts.desc(), ingest_queue.c.ingest_queue_id.desc()).limit(
                normalized_limit + 1
            )
        ).mappings()
    )

    items = [
        {
            "ingest_queue_id": str(row["ingest_queue_id"]),
            "payload_type": row["payload_type"],
            "path": _extract_queue_path(row["payload_json"]),
            "event_type": _queue_event_type(row["status"]),
            "event_ts": _iso_utc(row["event_ts"]),
            "status": row["status"],
            "last_error": row["last_error"],
        }
        for row in rows[:normalized_limit]
    ]
    has_more = len(rows) > normalized_limit
    next_cursor = None
    if has_more and items:
        last_row = rows[normalized_limit - 1]
        next_cursor = _encode_cursor(
            completed_ts=None,
            started_ts=_normalize_timestamp(last_row["event_ts"]),
            row_id=str(last_row["ingest_queue_id"]),
        )

    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


def _extract_queue_path(payload_json: Any) -> str | None:
    if not isinstance(payload_json, dict):
        return None
    path = payload_json.get("path")
    if path is None:
        return None
    return str(path)


def _polling_event_type(status: str) -> str:
    return "poll_completed" if status == "completed" else "poll_failed"


def _queue_event_type(status: str) -> str:
    return "queue_processing_completed" if status == "completed" else "queue_processing_failed"


def _encode_cursor(
    *,
    completed_ts: datetime | None,
    started_ts: datetime | None,
    row_id: str,
) -> str:
    payload = {
        "completed_ts": _iso_utc(completed_ts),
        "started_ts": _iso_utc(started_ts),
        "row_id": row_id,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(
    cursor: str | None,
    *,
    parameter_name: str,
) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        return {
            "completed_ts": _parse_cursor_timestamp(payload.get("completed_ts")),
            "started_ts": _parse_cursor_timestamp(payload.get("started_ts")),
            "row_id": str(payload["row_id"]),
        }
    except (KeyError, ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise InvalidOperationalActivityCursor(parameter_name) from exc


def _parse_cursor_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return _normalize_timestamp(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _polling_history_after_cursor(cursor: dict[str, Any]):
    cursor_completed_ts = cursor["completed_ts"]
    cursor_started_ts = cursor["started_ts"]
    cursor_row_id = cursor["row_id"]

    if cursor_completed_ts is None:
        return and_(
            ingest_runs.c.completed_ts.is_(None),
            or_(
                ingest_runs.c.started_ts < cursor_started_ts,
                and_(
                    ingest_runs.c.started_ts == cursor_started_ts,
                    ingest_runs.c.ingest_run_id < cursor_row_id,
                ),
            ),
        )

    return or_(
        ingest_runs.c.completed_ts.is_(None),
        ingest_runs.c.completed_ts < cursor_completed_ts,
        and_(
            ingest_runs.c.completed_ts == cursor_completed_ts,
            or_(
                ingest_runs.c.started_ts < cursor_started_ts,
                and_(
                    ingest_runs.c.started_ts == cursor_started_ts,
                    ingest_runs.c.ingest_run_id < cursor_row_id,
                ),
            ),
        ),
    )


def _queue_history_after_cursor(cursor: dict[str, Any], event_ts):
    cursor_event_ts = cursor["started_ts"]
    cursor_row_id = cursor["row_id"]

    return or_(
        event_ts < cursor_event_ts,
        and_(
            event_ts == cursor_event_ts,
            ingest_queue.c.ingest_queue_id < cursor_row_id,
        ),
    )


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
