from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.storage import photo_files, photos, watched_folders


def _watched_folder_id_for_root(root_path: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"watched-folder:{root_path}"))


def ensure_watched_folder_exists(
    connection: Connection,
    *,
    root_path: str,
    now: datetime,
) -> str:
    watched_folder_id = _watched_folder_id_for_root(root_path)
    row = connection.execute(
        select(watched_folders.c.watched_folder_id).where(
            watched_folders.c.watched_folder_id == watched_folder_id
        )
    ).first()
    if row is None:
        connection.execute(
            insert(watched_folders).values(
                watched_folder_id=watched_folder_id,
                root_path=root_path,
                display_name=root_path,
                is_enabled=1,
                availability_state="active",
                last_failure_reason=None,
                last_successful_scan_ts=None,
                created_ts=now,
                updated_ts=now,
            )
        )
        return watched_folder_id

    return watched_folder_id


def record_watched_folder_scan_success(
    connection: Connection,
    *,
    watched_folder_id: str,
    now: datetime,
) -> None:
    connection.execute(
        update(watched_folders)
        .where(watched_folders.c.watched_folder_id == watched_folder_id)
        .values(
            availability_state="active",
            last_failure_reason=None,
            last_successful_scan_ts=now,
            updated_ts=now,
        )
    )


def record_watched_folder_scan_failure(
    connection: Connection,
    *,
    watched_folder_id: str,
    reason: str,
    now: datetime,
) -> None:
    connection.execute(
        update(watched_folders)
        .where(watched_folders.c.watched_folder_id == watched_folder_id)
        .values(
            availability_state="unreachable",
            last_failure_reason=reason,
            updated_ts=now,
        )
    )


def ensure_watched_folder(
    connection: Connection,
    *,
    root_path: str,
    now: datetime,
) -> str:
    watched_folder_id = ensure_watched_folder_exists(
        connection,
        root_path=root_path,
        now=now,
    )
    record_watched_folder_scan_success(
        connection,
        watched_folder_id=watched_folder_id,
        now=now,
    )
    return watched_folder_id


def activate_observed_file(
    connection: Connection,
    *,
    watched_folder_id: str,
    photo_id: str,
    relative_path: str,
    filename: str,
    extension: str | None,
    filesize: int,
    created_ts: datetime,
    modified_ts: datetime,
    now: datetime,
) -> str:
    photo_file_id = str(uuid5(NAMESPACE_URL, f"photo-file:{watched_folder_id}:{relative_path}"))
    row = connection.execute(
        select(photo_files.c.photo_file_id).where(
            photo_files.c.photo_file_id == photo_file_id
        )
    ).first()
    values = {
        "photo_id": photo_id,
        "watched_folder_id": watched_folder_id,
        "relative_path": relative_path,
        "filename": filename,
        "extension": extension,
        "filesize": filesize,
        "created_ts": created_ts,
        "modified_ts": modified_ts,
        "last_seen_ts": now,
        "missing_ts": None,
        "deleted_ts": None,
        "lifecycle_state": "active",
        "absence_reason": None,
    }
    if row is None:
        connection.execute(
            insert(photo_files).values(
                photo_file_id=photo_file_id,
                first_seen_ts=now,
                **values,
            )
        )
    else:
        connection.execute(
            update(photo_files)
            .where(photo_files.c.photo_file_id == photo_file_id)
            .values(**values)
        )
    return photo_id


def reconcile_watched_folder(
    connection: Connection,
    *,
    watched_folder_id: str,
    observed_relative_paths: set[str],
    now: datetime,
    missing_file_grace_period_days: int,
) -> set[str]:
    touched_photo_ids: set[str] = set()
    rows = connection.execute(
        select(
            photo_files.c.photo_file_id,
            photo_files.c.photo_id,
            photo_files.c.relative_path,
            photo_files.c.missing_ts,
            photo_files.c.lifecycle_state,
        ).where(photo_files.c.watched_folder_id == watched_folder_id)
    ).mappings()

    for row in rows:
        if row["relative_path"] in observed_relative_paths:
            touched_photo_ids.add(row["photo_id"])
            continue

        touched_photo_ids.add(row["photo_id"])
        if row["lifecycle_state"] == "active":
            connection.execute(
                update(photo_files)
                .where(photo_files.c.photo_file_id == row["photo_file_id"])
                .values(
                    lifecycle_state="missing",
                    missing_ts=now,
                    deleted_ts=None,
                    absence_reason="path_removed",
                )
            )
            if missing_file_grace_period_days != 0:
                continue

        if row["lifecycle_state"] == "missing" or missing_file_grace_period_days == 0:
            missing_ts = normalize_timestamp(row["missing_ts"] or now)
            if missing_file_grace_period_days == 0 or (
                missing_ts + timedelta(days=missing_file_grace_period_days) <= now
            ):
                connection.execute(
                    update(photo_files)
                    .where(photo_files.c.photo_file_id == row["photo_file_id"])
                    .values(
                        lifecycle_state="deleted",
                        missing_ts=missing_ts,
                        deleted_ts=now,
                        absence_reason="path_removed",
                    )
                )

    return touched_photo_ids


def refresh_photo_deleted_timestamps(
    connection: Connection,
    *,
    photo_ids: set[str],
    now: datetime,
) -> None:
    for photo_id in photo_ids:
        file_rows = connection.execute(
            select(photo_files.c.lifecycle_state).where(photo_files.c.photo_id == photo_id)
        ).all()
        if not file_rows:
            connection.execute(
                update(photos)
                .where(photos.c.photo_id == photo_id)
                .values(deleted_ts=None)
            )
            continue

        all_deleted = all(row[0] == "deleted" for row in file_rows)
        connection.execute(
            update(photos)
            .where(photos.c.photo_id == photo_id)
            .values(deleted_ts=now if all_deleted else None)
        )


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
