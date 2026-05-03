from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from uuid import uuid4

from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Connection

from photoorg_db_schema import FACE_LABEL_SOURCE_HUMAN_CONFIRMED

from app.storage import face_labels, face_suggestions, faces, person_representations


SCORING_VERSION = "hybrid-v1"


@dataclass(frozen=True)
class _SuggestionCandidate:
    person_id: str
    confidence: float
    centroid_distance: float
    knn_distance: float
    representation_version: int
    model_version: str
    confirmed_face_count: int
    dispersion_score: float | None


def refresh_face_suggestions_for_person_scope(
    connection: Connection,
    *,
    person_id: str,
    limit: int = 5,
) -> None:
    del person_id
    face_rows = (
        connection.execute(
            select(faces.c.face_id)
            .where(
                faces.c.person_id.is_(None),
                faces.c.embedding.is_not(None),
            )
            .order_by(faces.c.face_id.asc())
        )
        .scalars()
        .all()
    )
    for face_id in face_rows:
        refresh_face_suggestions_for_face(
            connection,
            face_id=str(face_id),
            limit=limit,
        )


def refresh_face_suggestions_for_face(
    connection: Connection,
    *,
    face_id: str,
    limit: int = 5,
) -> None:
    source_row = (
        connection.execute(
            select(faces.c.face_id, faces.c.person_id, faces.c.embedding).where(
                faces.c.face_id == face_id
            )
        )
        .mappings()
        .first()
    )
    if source_row is None:
        return
    if source_row["person_id"] is not None:
        _delete_face_suggestions(connection, face_id=face_id)
        return

    source_embedding = _coerce_embedding(source_row["embedding"])
    if source_embedding is None:
        _delete_face_suggestions(connection, face_id=face_id)
        return

    representations = _load_person_representations(connection)
    if not representations:
        _delete_face_suggestions(connection, face_id=face_id)
        return
    person_ids = [representation["person_id"] for representation in representations]
    best_knn_distance = _load_best_knn_distance_by_person(
        connection,
        source_embedding=source_embedding,
        person_ids=person_ids,
    )

    ranked: list[_SuggestionCandidate] = []
    for representation in representations:
        centroid_distance = _cosine_distance(
            source_embedding,
            representation["centroid_embedding"],
        )
        if centroid_distance is None:
            continue
        person_id = representation["person_id"]
        knn_distance = best_knn_distance.get(person_id)
        if knn_distance is None:
            continue
        confidence = _combine_confidence(
            centroid_distance=centroid_distance,
            knn_distance=knn_distance,
            confirmed_face_count=representation["confirmed_face_count"],
            dispersion_score=representation["dispersion_score"],
        )
        ranked.append(
            _SuggestionCandidate(
                person_id=person_id,
                confidence=confidence,
                centroid_distance=centroid_distance,
                knn_distance=knn_distance,
                representation_version=representation["representation_version"],
                model_version=representation["model_version"],
                confirmed_face_count=representation["confirmed_face_count"],
                dispersion_score=representation["dispersion_score"],
            )
        )

    ranked.sort(key=lambda item: (-item.confidence, item.person_id))
    top_ranked = ranked[:limit]

    _delete_face_suggestions(connection, face_id=face_id)
    for rank, candidate in enumerate(top_ranked, start=1):
        connection.execute(
            insert(face_suggestions).values(
                face_suggestion_id=str(uuid4()),
                face_id=face_id,
                person_id=candidate.person_id,
                rank=rank,
                confidence=candidate.confidence,
                centroid_distance=candidate.centroid_distance,
                knn_distance=candidate.knn_distance,
                representation_version=candidate.representation_version,
                scoring_version=SCORING_VERSION,
                model_version=candidate.model_version,
                provenance={
                    "scoring_version": SCORING_VERSION,
                    "confirmed_face_count": candidate.confirmed_face_count,
                    "dispersion_score": candidate.dispersion_score,
                },
            )
        )


def _delete_face_suggestions(connection: Connection, *, face_id: str) -> None:
    connection.execute(delete(face_suggestions).where(face_suggestions.c.face_id == face_id))


def _load_person_representations(connection: Connection) -> list[dict[str, object]]:
    rows = (
        connection.execute(
            select(
                person_representations.c.person_id,
                person_representations.c.centroid_embedding,
                person_representations.c.confirmed_face_count,
                person_representations.c.dispersion_score,
                person_representations.c.representation_version,
                person_representations.c.model_version,
            ).where(
                person_representations.c.confirmed_face_count > 0,
                person_representations.c.centroid_embedding.is_not(None),
            )
        )
        .mappings()
        .all()
    )

    results: list[dict[str, object]] = []
    for row in rows:
        centroid_embedding = _coerce_embedding(row["centroid_embedding"])
        if centroid_embedding is None:
            continue
        results.append(
            {
                "person_id": str(row["person_id"]),
                "centroid_embedding": centroid_embedding,
                "confirmed_face_count": int(row["confirmed_face_count"]),
                "dispersion_score": (
                    float(row["dispersion_score"])
                    if row["dispersion_score"] is not None
                    else None
                ),
                "representation_version": int(row["representation_version"]),
                "model_version": str(row["model_version"]),
            }
        )
    return results


def _load_best_knn_distance_by_person(
    connection: Connection,
    *,
    source_embedding: list[float],
    person_ids: list[str],
) -> dict[str, float]:
    if not person_ids:
        return {}

    rows = (
        connection.execute(
            select(
                faces.c.face_id,
                face_labels.c.person_id,
                faces.c.embedding,
            )
            .select_from(face_labels.join(faces, face_labels.c.face_id == faces.c.face_id))
            .where(
                face_labels.c.person_id.in_(person_ids),
                face_labels.c.label_source == FACE_LABEL_SOURCE_HUMAN_CONFIRMED,
                faces.c.embedding.is_not(None),
            )
            .order_by(face_labels.c.person_id.asc(), faces.c.face_id.asc())
        )
        .mappings()
        .all()
    )

    best_distance: dict[str, float] = {}
    seen_faces: set[tuple[str, str]] = set()
    for row in rows:
        person_id = str(row["person_id"])
        face_id = str(row["face_id"])
        key = (person_id, face_id)
        if key in seen_faces:
            continue
        seen_faces.add(key)

        embedding = _coerce_embedding(row["embedding"])
        if embedding is None:
            continue
        distance = _cosine_distance(source_embedding, embedding)
        if distance is None:
            continue
        current = best_distance.get(person_id)
        if current is None or distance < current:
            best_distance[person_id] = distance
    return best_distance


def _combine_confidence(
    *,
    centroid_distance: float,
    knn_distance: float,
    confirmed_face_count: int,
    dispersion_score: float | None,
) -> float:
    centroid_confidence = _distance_to_confidence(centroid_distance)
    knn_confidence = _distance_to_confidence(knn_distance)
    reliability = min(1.0, max(0.0, confirmed_face_count / 5.0))
    reliability_multiplier = 0.75 + (0.25 * reliability)
    penalty = min(0.25, max(0.0, dispersion_score or 0.0))
    combined = ((centroid_confidence + knn_confidence) / 2.0) * reliability_multiplier - penalty
    return min(1.0, max(0.0, combined))


def _distance_to_confidence(distance: float) -> float:
    return min(1.0, max(0.0, 1.0 - float(distance)))


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


def _cosine_distance(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right):
        return None
    left_norm = sqrt(sum(component * component for component in left))
    right_norm = sqrt(sum(component * component for component in right))
    if left_norm == 0 or right_norm == 0:
        return None
    dot_product = sum(left_component * right_component for left_component, right_component in zip(left, right))
    similarity = dot_product / (left_norm * right_norm)
    bounded_similarity = min(1.0, max(-1.0, similarity))
    return 1.0 - bounded_similarity
