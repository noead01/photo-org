from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.storage import storage_source_aliases, storage_sources


class StorageSourceConflictError(RuntimeError):
    pass


def create_storage_source(
    connection: Connection,
    *,
    display_name: str,
    marker_filename: str,
    marker_version: int,
    now: datetime,
) -> dict[str, object]:
    storage_source_id = str(uuid4())
    values = {
        "storage_source_id": storage_source_id,
        "display_name": display_name,
        "marker_filename": marker_filename,
        "marker_version": marker_version,
        "availability_state": "unknown",
        "last_failure_reason": None,
        "last_validated_ts": None,
        "created_ts": now,
        "updated_ts": now,
    }
    connection.execute(insert(storage_sources).values(**values))
    return values


def get_storage_source_by_marker_id(
    connection: Connection,
    storage_source_id: str,
) -> dict[str, object] | None:
    return connection.execute(
        select(storage_sources).where(storage_sources.c.storage_source_id == storage_source_id)
    ).mappings().first()


def attach_storage_source_alias(
    connection: Connection,
    *,
    storage_source_id: str,
    alias_path: str,
    now: datetime,
) -> dict[str, object]:
    existing = connection.execute(
        select(storage_source_aliases).where(storage_source_aliases.c.alias_path == alias_path)
    ).mappings().first()
    if existing is not None:
        if existing["storage_source_id"] != storage_source_id:
            raise StorageSourceConflictError(
                f"alias_path {alias_path!r} already belongs to storage_source_id "
                f"{existing['storage_source_id']}"
            )
        connection.execute(
            update(storage_source_aliases)
            .where(storage_source_aliases.c.storage_source_alias_id == existing["storage_source_alias_id"])
            .values(updated_ts=now)
        )
        return {
            **existing,
            "updated_ts": now,
        }

    values = {
        "storage_source_alias_id": str(uuid4()),
        "storage_source_id": storage_source_id,
        "alias_path": alias_path,
        "created_ts": now,
        "updated_ts": now,
    }
    connection.execute(insert(storage_source_aliases).values(**values))
    return values


def list_storage_source_aliases(
    connection: Connection,
    storage_source_id: str,
) -> list[dict[str, object]]:
    return list(
        connection.execute(
            select(storage_source_aliases)
            .where(storage_source_aliases.c.storage_source_id == storage_source_id)
            .order_by(storage_source_aliases.c.alias_path)
        ).mappings()
    )


def update_storage_source_availability(
    connection: Connection,
    *,
    storage_source_id: str,
    availability_state: str,
    last_failure_reason: str | None,
    now: datetime,
) -> None:
    connection.execute(
        update(storage_sources)
        .where(storage_sources.c.storage_source_id == storage_source_id)
        .values(
            availability_state=availability_state,
            last_failure_reason=last_failure_reason,
            last_validated_ts=now,
            updated_ts=now,
        )
    )
