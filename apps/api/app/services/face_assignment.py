from __future__ import annotations

from uuid import uuid4

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from photoorg_db_schema import (
    FACE_LABEL_SOURCE_HUMAN_CONFIRMED,
    FACE_LABEL_SOURCE_MACHINE_APPLIED,
    FACE_LABEL_SOURCE_MACHINE_SUGGESTED,
)

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


def assign_face_to_person(
    connection: Connection,
    *,
    face_id: str,
    person_id: str,
) -> dict[str, str]:
    try:
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
    except IntegrityError as exc:
        _raise_person_not_found_on_fk_violation(
            connection,
            person_id=person_id,
            exc=exc,
        )

    row = _face_row(connection, face_id)
    if row is None:
        raise FaceNotFoundError("Face not found")
    if row["person_id"] is not None:
        raise FaceAlreadyAssignedError("Face already assigned")

    if not _person_exists(connection, person_id):
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

    if not _person_exists(connection, person_id):
        raise PersonNotFoundError("Person not found")

    try:
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
    except IntegrityError as exc:
        _raise_person_not_found_on_fk_violation(
            connection,
            person_id=person_id,
            exc=exc,
        )

    return {
        "face_id": row["face_id"],
        "photo_id": row["photo_id"],
        "previous_person_id": previous_person_id,
        "person_id": person_id,
    }


def auto_apply_face_suggestion(
    connection: Connection,
    *,
    face_id: str,
    person_id: str,
    confidence: float,
    matched_face_id: str,
    review_threshold: float,
    auto_accept_threshold: float,
) -> dict[str, object] | None:
    if not _person_exists(connection, person_id):
        return None

    try:
        result = connection.execute(
            update(faces)
            .where(
                faces.c.face_id == face_id,
                faces.c.person_id.is_(None),
            )
            .values(person_id=person_id)
        )
    except IntegrityError as exc:
        _raise_person_not_found_on_fk_violation(
            connection,
            person_id=person_id,
            exc=exc,
        )
        return None

    if result.rowcount != 1:
        return None

    assignment = _face_assignment(connection, face_id)
    _persist_machine_applied_face_label_event(
        connection,
        face_id=face_id,
        person_id=person_id,
        confidence=confidence,
        matched_face_id=matched_face_id,
        review_threshold=review_threshold,
        auto_accept_threshold=auto_accept_threshold,
    )
    return {
        **assignment,
        "confidence": float(confidence),
    }


def record_review_needed_face_suggestion(
    connection: Connection,
    *,
    face_id: str,
    person_id: str,
    confidence: float,
    matched_face_id: str,
    review_threshold: float,
    auto_accept_threshold: float,
) -> dict[str, object] | None:
    face_row = _face_row(connection, face_id)
    if face_row is None:
        return None
    if face_row["person_id"] is not None:
        return None
    if not _person_exists(connection, person_id):
        return None

    _upsert_machine_suggested_face_label_state(
        connection,
        face_id=face_id,
        person_id=person_id,
        confidence=confidence,
        matched_face_id=matched_face_id,
        review_threshold=review_threshold,
        auto_accept_threshold=auto_accept_threshold,
    )

    return {
        "face_id": str(face_row["face_id"]),
        "photo_id": str(face_row["photo_id"]),
        "person_id": person_id,
        "confidence": float(confidence),
        "matched_face_id": matched_face_id,
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


def _person_exists(connection: Connection, person_id: str) -> bool:
    return (
        connection.execute(
            select(people.c.person_id).where(people.c.person_id == person_id)
        ).scalar_one_or_none()
        is not None
    )


def _raise_person_not_found_on_fk_violation(
    connection: Connection,
    *,
    person_id: str,
    exc: IntegrityError,
) -> None:
    if not _person_exists(connection, person_id):
        raise PersonNotFoundError("Person not found") from exc
    raise exc


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
            label_source=FACE_LABEL_SOURCE_HUMAN_CONFIRMED,
            confidence=None,
            model_version=None,
            provenance=provenance,
        )
    )


def _persist_machine_applied_face_label_event(
    connection: Connection,
    *,
    face_id: str,
    person_id: str,
    confidence: float,
    matched_face_id: str,
    review_threshold: float,
    auto_accept_threshold: float,
) -> None:
    connection.execute(
        insert(face_labels).values(
            face_label_id=str(uuid4()),
            face_id=face_id,
            person_id=person_id,
            label_source=FACE_LABEL_SOURCE_MACHINE_APPLIED,
            confidence=float(confidence),
            model_version=None,
            provenance={
                "workflow": "recognition-suggestions",
                "surface": "api",
                "action": "auto_apply",
                "matched_face_id": matched_face_id,
                "review_threshold": float(review_threshold),
                "auto_accept_threshold": float(auto_accept_threshold),
            },
        )
    )


def _upsert_machine_suggested_face_label_state(
    connection: Connection,
    *,
    face_id: str,
    person_id: str,
    confidence: float,
    matched_face_id: str,
    review_threshold: float,
    auto_accept_threshold: float,
) -> None:
    existing_rows = (
        connection.execute(
            select(
                face_labels.c.face_label_id,
                face_labels.c.person_id,
            ).where(
                face_labels.c.face_id == face_id,
                face_labels.c.label_source == FACE_LABEL_SOURCE_MACHINE_SUGGESTED,
            )
        )
        .mappings()
        .all()
    )
    matched_existing_row = next(
        (row for row in existing_rows if str(row["person_id"]) == person_id),
        None,
    )
    provenance = {
        "workflow": "recognition-suggestions",
        "surface": "api",
        "action": "review_needed",
        "matched_face_id": matched_face_id,
        "review_threshold": float(review_threshold),
        "auto_accept_threshold": float(auto_accept_threshold),
    }
    if matched_existing_row is not None:
        matched_face_label_id = str(matched_existing_row["face_label_id"])
        connection.execute(
            update(face_labels)
            .where(face_labels.c.face_label_id == matched_face_label_id)
            .values(
                confidence=float(confidence),
                model_version=None,
                provenance=provenance,
                updated_ts=func.current_timestamp(),
            )
        )
        stale_ids = [
            str(row["face_label_id"])
            for row in existing_rows
            if str(row["face_label_id"]) != matched_face_label_id
        ]
        if stale_ids:
            connection.execute(
                delete(face_labels).where(face_labels.c.face_label_id.in_(stale_ids))
            )
        return

    if existing_rows:
        connection.execute(
            delete(face_labels).where(
                face_labels.c.face_id == face_id,
                face_labels.c.label_source == FACE_LABEL_SOURCE_MACHINE_SUGGESTED,
            )
        )
    connection.execute(
        insert(face_labels).values(
            face_label_id=str(uuid4()),
            face_id=face_id,
            person_id=person_id,
            label_source=FACE_LABEL_SOURCE_MACHINE_SUGGESTED,
            confidence=float(confidence),
            model_version=None,
            provenance=provenance,
        )
    )
