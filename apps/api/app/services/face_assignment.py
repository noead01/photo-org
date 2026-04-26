from __future__ import annotations

from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.storage import face_labels, faces, people


class FaceNotFoundError(LookupError):
    pass


class PersonNotFoundError(LookupError):
    pass


class FaceAlreadyAssignedError(RuntimeError):
    pass


class FaceNotAssignedError(RuntimeError):
    pass


class FaceAlreadyAssignedToPersonError(RuntimeError):
    pass


_MANUAL_LABEL_SOURCE = "manual"


def assign_face_to_person(
    connection: Connection,
    *,
    face_id: str,
    person_id: str,
) -> dict[str, str]:
    result = connection.execute(
        update(faces)
        .where(
            faces.c.face_id == face_id,
            faces.c.person_id.is_(None),
            select(people.c.person_id).where(people.c.person_id == person_id).exists(),
        )
        .values(person_id=person_id)
    )
    if result.rowcount == 1:
        assignment = _face_assignment(connection, face_id)
        _persist_face_label_event(
            connection,
            face_id=face_id,
            person_id=person_id,
            action="assignment",
        )
        return assignment

    row = _face_row(connection, face_id)
    if row is None:
        raise FaceNotFoundError("Face not found")
    if row["person_id"] is not None:
        raise FaceAlreadyAssignedError("Face already assigned")

    person_exists = (
        connection.execute(
            select(people.c.person_id).where(people.c.person_id == person_id)
        ).scalar_one_or_none()
        is not None
    )
    if not person_exists:
        raise PersonNotFoundError("Person not found")

    raise FaceAlreadyAssignedError("Face already assigned")


def reassign_face_to_person(
    connection: Connection,
    *,
    face_id: str,
    person_id: str,
) -> dict[str, str]:
    row = _face_row(connection, face_id)
    if row is None:
        raise FaceNotFoundError("Face not found")

    previous_person_id = row["person_id"]
    if previous_person_id is None:
        raise FaceNotAssignedError("Face is not assigned")
    if previous_person_id == person_id:
        raise FaceAlreadyAssignedToPersonError("Face already assigned to person")

    person_exists = (
        connection.execute(
            select(people.c.person_id).where(people.c.person_id == person_id)
        ).scalar_one_or_none()
        is not None
    )
    if not person_exists:
        raise PersonNotFoundError("Person not found")

    result = connection.execute(
        update(faces)
        .where(
            faces.c.face_id == face_id,
            faces.c.person_id == previous_person_id,
        )
        .values(person_id=person_id)
    )
    if result.rowcount != 1:
        raise FaceAlreadyAssignedError("Face assignment changed; retry correction")

    _persist_face_label_event(
        connection,
        face_id=face_id,
        person_id=person_id,
        action="correction",
        previous_person_id=previous_person_id,
    )

    return {
        "face_id": row["face_id"],
        "photo_id": row["photo_id"],
        "previous_person_id": previous_person_id,
        "person_id": person_id,
    }


def _face_row(connection: Connection, face_id: str):
    return (
        connection.execute(
            select(
                faces.c.face_id,
                faces.c.photo_id,
                faces.c.person_id,
            ).where(faces.c.face_id == face_id)
        )
        .mappings()
        .first()
    )


def _face_assignment(connection: Connection, face_id: str) -> dict[str, str]:
    row = _face_row(connection, face_id)
    if row is None:
        raise FaceNotFoundError("Face not found")
    person_id = row["person_id"]
    if person_id is None:
        raise RuntimeError("Face assignment persisted without person_id")
    return {
        "face_id": row["face_id"],
        "photo_id": row["photo_id"],
        "person_id": person_id,
    }


def _persist_face_label_event(
    connection: Connection,
    *,
    face_id: str,
    person_id: str,
    action: str,
    previous_person_id: str | None = None,
) -> None:
    provenance: dict[str, object] = {
        "workflow": "face-labeling",
        "surface": "api",
        "action": action,
    }
    if previous_person_id is not None:
        provenance["previous_person_id"] = previous_person_id

    connection.execute(
        insert(face_labels).values(
            face_label_id=str(uuid4()),
            face_id=face_id,
            person_id=person_id,
            label_source=_MANUAL_LABEL_SOURCE,
            confidence=None,
            model_version=None,
            provenance=provenance,
        )
    )
