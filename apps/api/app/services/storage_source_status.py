from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from app.storage import ingest_runs, photo_files, photos, storage_source_aliases, storage_sources, watched_folders


@dataclass(frozen=True)
class LatestIngestRunSummary:
    status: str
    files_seen: int
    files_created: int
    files_updated: int
    files_missing: int
    error_count: int
    error_summary: str | None
    completed_ts: datetime | None


def list_storage_source_statuses(connection: Connection) -> list[dict[str, Any]]:
    sources = list(
        connection.execute(
            select(storage_sources).order_by(storage_sources.c.created_ts, storage_sources.c.storage_source_id)
        ).mappings()
    )
    return [_build_storage_source_status(connection, source) for source in sources]


def get_storage_source_status(connection: Connection, storage_source_id: str) -> dict[str, Any] | None:
    source = connection.execute(
        select(storage_sources).where(storage_sources.c.storage_source_id == storage_source_id)
    ).mappings().first()
    if source is None:
        return None
    return _build_storage_source_status(connection, source)


def list_watched_folder_statuses(
    connection: Connection,
    storage_source_id: str,
) -> list[dict[str, Any]]:
    rows = list(
        connection.execute(
            select(watched_folders)
            .where(watched_folders.c.storage_source_id == storage_source_id)
            .order_by(watched_folders.c.relative_path, watched_folders.c.watched_folder_id)
        ).mappings()
    )
    return [
        {
            **dict(row),
            "latest_ingest_run": _serialize_ingest_run_summary(
                _load_latest_ingest_run_for_watched_folder(connection, str(row["watched_folder_id"]))
            ),
        }
        for row in rows
    ]


def _build_storage_source_status(connection: Connection, source: dict[str, Any]) -> dict[str, Any]:
    storage_source_id = str(source["storage_source_id"])
    watched_folder_rows = list_watched_folder_statuses(connection, storage_source_id)
    active_photo_count = _count_queryable_photos(connection, storage_source_id)
    thumbnail_count = _count_photos_with_thumbnails(connection, storage_source_id)
    latest_run = _load_latest_ingest_run_for_source(connection, storage_source_id)
    return {
        **dict(source),
        "alias_paths": _list_alias_paths(connection, storage_source_id),
        "watched_folder_count": len(watched_folder_rows),
        "unreachable_watched_folder_count": sum(
            1 for row in watched_folder_rows if row["availability_state"] != "active"
        ),
        "catalog": {
            "metadata_queryable": active_photo_count > 0,
            "thumbnails_available": thumbnail_count > 0,
            "originals_available": source["availability_state"] == "active",
        },
        "latest_ingest_run": _serialize_ingest_run_summary(latest_run),
        "recent_failures": _list_recent_failures(connection, storage_source_id),
    }


def _list_alias_paths(connection: Connection, storage_source_id: str) -> list[str]:
    return list(
        connection.execute(
            select(storage_source_aliases.c.alias_path)
            .where(storage_source_aliases.c.storage_source_id == storage_source_id)
            .order_by(storage_source_aliases.c.alias_path)
        ).scalars()
    )


def _count_queryable_photos(connection: Connection, storage_source_id: str) -> int:
    return int(
        connection.execute(
            select(func.count(func.distinct(photo_files.c.photo_id)))
            .select_from(
                photo_files.join(
                    watched_folders,
                    photo_files.c.watched_folder_id == watched_folders.c.watched_folder_id,
                ).join(photos, photo_files.c.photo_id == photos.c.photo_id)
            )
            .where(watched_folders.c.storage_source_id == storage_source_id)
            .where(photo_files.c.deleted_ts.is_(None))
            .where(photo_files.c.lifecycle_state == "active")
            .where(photos.c.deleted_ts.is_(None))
        ).scalar_one()
    )


def _count_photos_with_thumbnails(connection: Connection, storage_source_id: str) -> int:
    return int(
        connection.execute(
            select(func.count(func.distinct(photo_files.c.photo_id)))
            .select_from(
                photo_files.join(
                    watched_folders,
                    photo_files.c.watched_folder_id == watched_folders.c.watched_folder_id,
                ).join(photos, photo_files.c.photo_id == photos.c.photo_id)
            )
            .where(watched_folders.c.storage_source_id == storage_source_id)
            .where(photo_files.c.deleted_ts.is_(None))
            .where(photo_files.c.lifecycle_state == "active")
            .where(photos.c.deleted_ts.is_(None))
            .where(photos.c.thumbnail_jpeg.is_not(None))
        ).scalar_one()
    )


def _load_latest_ingest_run_for_source(
    connection: Connection,
    storage_source_id: str,
) -> LatestIngestRunSummary | None:
    watched_folder_ids = list(
        connection.execute(
            select(watched_folders.c.watched_folder_id).where(
                watched_folders.c.storage_source_id == storage_source_id
            )
        ).scalars()
    )
    if not watched_folder_ids:
        return None
    row = connection.execute(
        select(ingest_runs)
        .where(ingest_runs.c.watched_folder_id.in_(watched_folder_ids))
        .order_by(
            ingest_runs.c.completed_ts.desc().nullslast(),
            ingest_runs.c.started_ts.desc(),
            ingest_runs.c.ingest_run_id.desc(),
        )
    ).mappings().first()
    return _ingest_run_summary_from_row(row)


def _load_latest_ingest_run_for_watched_folder(
    connection: Connection,
    watched_folder_id: str,
) -> LatestIngestRunSummary | None:
    row = connection.execute(
        select(ingest_runs)
        .where(ingest_runs.c.watched_folder_id == watched_folder_id)
        .order_by(
            ingest_runs.c.completed_ts.desc().nullslast(),
            ingest_runs.c.started_ts.desc(),
            ingest_runs.c.ingest_run_id.desc(),
        )
    ).mappings().first()
    return _ingest_run_summary_from_row(row)


def _list_recent_failures(connection: Connection, storage_source_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(ingest_runs.c.watched_folder_id, ingest_runs.c.status, ingest_runs.c.error_summary, ingest_runs.c.completed_ts)
        .select_from(
            ingest_runs.join(
                watched_folders,
                ingest_runs.c.watched_folder_id == watched_folders.c.watched_folder_id,
            )
        )
        .where(watched_folders.c.storage_source_id == storage_source_id)
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
            "watched_folder_id": row["watched_folder_id"],
            "status": row["status"],
            "error_summary": row["error_summary"],
            "completed_ts": _iso_utc(row["completed_ts"]),
        }
        for row in rows
    ]


def _ingest_run_summary_from_row(row: dict[str, Any] | None) -> LatestIngestRunSummary | None:
    if row is None:
        return None
    return LatestIngestRunSummary(
        status=str(row["status"]),
        files_seen=int(row["files_seen"] or 0),
        files_created=int(row["files_created"] or 0),
        files_updated=int(row["files_updated"] or 0),
        files_missing=int(row["files_missing"] or 0),
        error_count=int(row["error_count"] or 0),
        error_summary=row["error_summary"],
        completed_ts=_normalize_timestamp(row["completed_ts"]),
    )


def _serialize_ingest_run_summary(summary: LatestIngestRunSummary | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    return {
        "status": summary.status,
        "files_seen": summary.files_seen,
        "files_created": summary.files_created,
        "files_updated": summary.files_updated,
        "files_missing": summary.files_missing,
        "error_count": summary.error_count,
        "error_summary": summary.error_summary,
        "completed_ts": _iso_utc(summary.completed_ts),
    }


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
