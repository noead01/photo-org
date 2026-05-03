from __future__ import annotations

from math import sqrt

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Connection

from photoorg_db_schema import FACE_LABEL_SOURCE_HUMAN_CONFIRMED

from app.services.recognition_policy import resolve_prediction_metadata
from app.storage import face_labels, faces, person_representations


def refresh_person_representation(connection: Connection, *, person_id: str) -> None:
    embeddings = _load_confirmed_embeddings(connection, person_id=person_id)
    if not embeddings:
        connection.execute(
            delete(person_representations).where(person_representations.c.person_id == person_id)
        )
        return

    centroid = _average_embedding(embeddings)
    dispersion = _mean_cosine_distance(embeddings, centroid)
    current_version = connection.execute(
        select(person_representations.c.representation_version).where(
            person_representations.c.person_id == person_id
        )
    ).scalar_one_or_none()
    next_version = int(current_version) + 1 if current_version is not None else 1
    prediction_metadata = resolve_prediction_metadata()

    update_result = connection.execute(
        update(person_representations)
        .where(person_representations.c.person_id == person_id)
        .values(
            centroid_embedding=centroid,
            confirmed_face_count=len(embeddings),
            dispersion_score=dispersion,
            representation_version=next_version,
            computed_ts=func.current_timestamp(),
            model_version=prediction_metadata["model_version"],
            provenance={"source": "human_confirmed_faces", "face_count": len(embeddings)},
        )
    )
    if update_result.rowcount == 1:
        return

    connection.execute(
        insert(person_representations).values(
            person_id=person_id,
            centroid_embedding=centroid,
            confirmed_face_count=len(embeddings),
            dispersion_score=dispersion,
            representation_version=next_version,
            model_version=prediction_metadata["model_version"],
            provenance={"source": "human_confirmed_faces", "face_count": len(embeddings)},
        )
    )


def _load_confirmed_embeddings(connection: Connection, *, person_id: str) -> list[list[float]]:
    rows = (
        connection.execute(
            select(faces.c.face_id, faces.c.embedding)
            .select_from(face_labels.join(faces, face_labels.c.face_id == faces.c.face_id))
            .where(
                face_labels.c.person_id == person_id,
                face_labels.c.label_source == FACE_LABEL_SOURCE_HUMAN_CONFIRMED,
                faces.c.embedding.is_not(None),
            )
            .order_by(faces.c.face_id.asc(), face_labels.c.updated_ts.desc())
        )
        .mappings()
        .all()
    )

    seen_face_ids: set[str] = set()
    embeddings: list[list[float]] = []
    expected_dim: int | None = None
    for row in rows:
        face_id = str(row["face_id"])
        if face_id in seen_face_ids:
            continue
        seen_face_ids.add(face_id)

        embedding = _coerce_embedding(row["embedding"])
        if embedding is None:
            continue
        if expected_dim is None:
            expected_dim = len(embedding)
        if len(embedding) != expected_dim:
            continue
        embeddings.append(embedding)
    return embeddings


def _coerce_embedding(value: object) -> list[float] | None:
    if value is None:
        return None
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list | tuple):
        return None
    try:
        return [float(component) for component in value]
    except (TypeError, ValueError):
        return None


def _average_embedding(embeddings: list[list[float]]) -> list[float]:
    size = len(embeddings)
    dimension = len(embeddings[0])
    totals = [0.0] * dimension
    for embedding in embeddings:
        for index, value in enumerate(embedding):
            totals[index] += value
    return [total / size for total in totals]


def _mean_cosine_distance(embeddings: list[list[float]], centroid: list[float]) -> float | None:
    distances: list[float] = []
    for embedding in embeddings:
        distance = _cosine_distance(embedding, centroid)
        if distance is not None:
            distances.append(distance)
    if not distances:
        return None
    return sum(distances) / len(distances)


def _cosine_distance(left: list[float], right: list[float]) -> float | None:
    left_norm = sqrt(sum(component * component for component in left))
    right_norm = sqrt(sum(component * component for component in right))
    if left_norm == 0 or right_norm == 0:
        return None
    dot_product = sum(left_component * right_component for left_component, right_component in zip(left, right))
    similarity = dot_product / (left_norm * right_norm)
    bounded_similarity = min(1.0, max(-1.0, similarity))
    return 1.0 - bounded_similarity
