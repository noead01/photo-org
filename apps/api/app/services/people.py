from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection

from app.storage import face_labels, faces, people


class PersonNotFoundError(LookupError):
    pass


class PersonInUseError(RuntimeError):
    pass


def _normalize_display_name(display_name: str) -> str:
    return display_name.strip()


def create_person(
    connection: Connection,
    *,
    display_name: str,
    now: datetime,
) -> dict[str, object]:
    person_id = str(uuid4())
    normalized_display_name = _normalize_display_name(display_name)
    row = {
        "person_id": person_id,
        "display_name": normalized_display_name,
        "created_ts": now,
        "updated_ts": now,
    }
    connection.execute(insert(people).values(row))
    return row


def list_people(connection: Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        select(people).order_by(people.c.display_name, people.c.person_id)
    ).mappings()
    return [_person_from_row(row) for row in rows]


def get_person(connection: Connection, person_id: str) -> dict[str, object] | None:
    row = (
        connection.execute(select(people).where(people.c.person_id == person_id))
        .mappings()
        .first()
    )
    if row is None:
        return None
    return _person_from_row(row)


def update_person(
    connection: Connection,
    *,
    person_id: str,
    display_name: str,
    now: datetime,
) -> dict[str, object]:
    normalized_display_name = _normalize_display_name(display_name)
    result = connection.execute(
        update(people)
        .where(people.c.person_id == person_id)
        .values(display_name=normalized_display_name, updated_ts=now)
    )
    if result.rowcount == 0:
        raise PersonNotFoundError("Person not found")

    person = get_person(connection, person_id)
    if person is None:
        raise PersonNotFoundError("Person not found")
    return person


def delete_person(connection: Connection, person_id: str) -> None:
    delete_result = connection.execute(
        delete(people).where(
            people.c.person_id == person_id,
            ~select(faces.c.face_id).where(faces.c.person_id == person_id).exists(),
            ~select(face_labels.c.face_label_id)
            .where(face_labels.c.person_id == person_id)
            .exists(),
        )
    )
    if delete_result.rowcount == 1:
        return

    person = get_person(connection, person_id)
    if person is None:
        raise PersonNotFoundError("Person not found")
    raise PersonInUseError("Person is referenced by face or label data")


def _normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _person_from_row(row: Any) -> dict[str, object]:
    return {
        "person_id": row["person_id"],
        "display_name": row["display_name"],
        "created_ts": _normalize_utc_datetime(row["created_ts"]),
        "updated_ts": _normalize_utc_datetime(row["updated_ts"]),
    }
