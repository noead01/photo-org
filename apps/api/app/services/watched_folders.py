from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection

from app.storage import storage_source_aliases, watched_folders


class WatchedFolderValidationError(RuntimeError):
    pass


def create_watched_folder(
    connection: Connection,
    *,
    storage_source_id: str,
    alias_path: str,
    watched_path: str,
    display_name: str | None,
    now: datetime,
) -> dict[str, object]:
    normalized_alias_path = _normalize_path(alias_path)
    normalized_watched_path = _normalize_path(watched_path)
    _validate_alias_belongs_to_source(
        connection,
        storage_source_id=storage_source_id,
        alias_path=normalized_alias_path,
    )
    relative_path = _relative_path_within_source(
        alias_path=normalized_alias_path,
        watched_path=normalized_watched_path,
    )
    watched_folder_id = _watched_folder_id_for_scan_path(normalized_watched_path)

    existing = connection.execute(
        select(watched_folders).where(
            (watched_folders.c.watched_folder_id == watched_folder_id)
            | (
                (watched_folders.c.storage_source_id == storage_source_id)
                & (watched_folders.c.relative_path == relative_path)
            )
            | (watched_folders.c.scan_path == normalized_watched_path)
        )
    ).mappings().first()
    values = {
        "storage_source_id": storage_source_id,
        "scan_path": normalized_watched_path,
        "container_mount_path": normalized_watched_path,
        "relative_path": relative_path,
        "display_name": display_name or PurePosixPath(relative_path).name or relative_path,
        "is_enabled": 1,
        "updated_ts": now,
    }
    if existing is not None:
        connection.execute(
            update(watched_folders)
            .where(watched_folders.c.watched_folder_id == existing["watched_folder_id"])
            .values(**values)
        )
        return {
            **existing,
            **values,
        }

    record = {
        "watched_folder_id": watched_folder_id,
        "availability_state": "active",
        "last_failure_reason": None,
        "last_successful_scan_ts": None,
        "created_ts": now,
        **values,
    }
    connection.execute(insert(watched_folders).values(**record))
    return record


def list_watched_folders(
    connection: Connection,
    storage_source_id: str,
) -> list[dict[str, object]]:
    return list(
        connection.execute(
            select(watched_folders)
            .where(watched_folders.c.storage_source_id == storage_source_id)
            .order_by(watched_folders.c.relative_path)
        ).mappings()
    )


def set_watched_folder_enabled(
    connection: Connection,
    *,
    storage_source_id: str,
    watched_folder_id: str,
    is_enabled: bool,
    now: datetime,
) -> dict[str, object]:
    row = _get_scoped_watched_folder(
        connection,
        storage_source_id=storage_source_id,
        watched_folder_id=watched_folder_id,
    )
    values = {
        "is_enabled": 1 if is_enabled else 0,
        "updated_ts": now,
    }
    connection.execute(
        update(watched_folders)
        .where(watched_folders.c.watched_folder_id == watched_folder_id)
        .values(**values)
    )
    return {
        **row,
        **values,
    }


def remove_watched_folder(
    connection: Connection,
    *,
    storage_source_id: str,
    watched_folder_id: str,
) -> None:
    _get_scoped_watched_folder(
        connection,
        storage_source_id=storage_source_id,
        watched_folder_id=watched_folder_id,
    )
    connection.execute(
        delete(watched_folders).where(
            watched_folders.c.watched_folder_id == watched_folder_id,
            watched_folders.c.storage_source_id == storage_source_id,
        )
    )


def _validate_alias_belongs_to_source(
    connection: Connection,
    *,
    storage_source_id: str,
    alias_path: str,
) -> None:
    alias_row = connection.execute(
        select(storage_source_aliases.c.storage_source_alias_id).where(
            storage_source_aliases.c.storage_source_id == storage_source_id,
            storage_source_aliases.c.alias_path == alias_path,
        )
    ).first()
    if alias_row is None:
        raise WatchedFolderValidationError(
            f"alias_path {alias_path!r} is not registered for storage_source_id {storage_source_id}"
        )


def _relative_path_within_source(*, alias_path: str, watched_path: str) -> str:
    alias = PurePosixPath(alias_path)
    watched = PurePosixPath(watched_path)
    try:
        relative = watched.relative_to(alias)
    except ValueError as exc:
        raise WatchedFolderValidationError(
            f"watched_path {watched_path!r} is outside source boundary {alias_path!r}"
        ) from exc
    if str(relative) in {"", "."}:
        return "."
    return str(relative)


def _get_scoped_watched_folder(
    connection: Connection,
    *,
    storage_source_id: str,
    watched_folder_id: str,
) -> dict[str, object]:
    row = connection.execute(
        select(watched_folders).where(
            watched_folders.c.watched_folder_id == watched_folder_id,
            watched_folders.c.storage_source_id == storage_source_id,
        )
    ).mappings().first()
    if row is None:
        raise LookupError(f"missing watched folder {watched_folder_id} for storage source {storage_source_id}")
    return row


def _watched_folder_id_for_scan_path(scan_path: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"watched-folder:{scan_path}"))


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if not normalized:
        return "/"
    raw_parts = normalized.split("/")
    parts: list[str] = []
    for part in raw_parts:
        if not part or part == ".":
            continue
        if part == "..":
            raise WatchedFolderValidationError(f"path {value!r} must not contain '..'")
        parts.append(part)
    if normalized.startswith("//"):
        prefix = "//"
    elif normalized.startswith("/"):
        prefix = "/"
    else:
        prefix = ""
    if not parts:
        return prefix or "/"
    return prefix + "/".join(parts)
