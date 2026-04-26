from __future__ import annotations

from math import sqrt

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from app.services.recognition_policy import (
    SUGGESTION_DECISION_NO_SUGGESTION,
    classify_suggestion_confidence,
    distance_to_confidence,
    resolve_suggestion_thresholds,
)
from app.storage import faces, people


class FaceNotFoundError(LookupError):
    pass


class FaceEmbeddingNotAvailableError(RuntimeError):
    pass


def lookup_nearest_neighbor_candidates(
    connection: Connection,
    *,
    face_id: str,
    limit: int = 5,
) -> dict[str, object]:
    source_row = (
        connection.execute(
            select(faces.c.face_id, faces.c.embedding).where(faces.c.face_id == face_id)
        )
        .mappings()
        .first()
    )
    if source_row is None:
        raise FaceNotFoundError("Face not found")

    source_embedding = _coerce_embedding(source_row["embedding"])
    if source_embedding is None:
        raise FaceEmbeddingNotAvailableError("Face embedding not available")
    if connection.dialect.name == "postgresql":
        ordered_candidates = _lookup_candidates_postgresql(
            connection,
            face_id=face_id,
            source_embedding=source_embedding,
            limit=limit,
        )
    else:
        ordered_candidates = _lookup_candidates_python(
            connection,
            face_id=face_id,
            source_embedding=source_embedding,
        )
    candidates_with_confidence = _with_candidate_confidence(ordered_candidates)
    thresholds = resolve_suggestion_thresholds()
    top_candidate_confidence = (
        float(candidates_with_confidence[0]["confidence"]) if candidates_with_confidence else None
    )
    if top_candidate_confidence is None:
        suggestion_decision = SUGGESTION_DECISION_NO_SUGGESTION
    else:
        suggestion_decision = classify_suggestion_confidence(
            top_candidate_confidence,
            review_threshold=thresholds["review_threshold"],
            auto_accept_threshold=thresholds["auto_accept_threshold"],
        )
    if suggestion_decision == SUGGESTION_DECISION_NO_SUGGESTION:
        candidates = []
    else:
        candidates = candidates_with_confidence[:limit]

    return {
        "face_id": face_id,
        "candidates": candidates,
        "suggestion_policy": {
            "decision": suggestion_decision,
            "review_threshold": thresholds["review_threshold"],
            "auto_accept_threshold": thresholds["auto_accept_threshold"],
            "top_candidate_confidence": top_candidate_confidence,
        },
    }


def _lookup_candidates_postgresql(
    connection: Connection,
    *,
    face_id: str,
    source_embedding: list[float],
    limit: int,
) -> list[dict[str, object]]:
    distance_expression = faces.c.embedding.cosine_distance(source_embedding)
    ranked_candidates = (
        select(
            faces.c.person_id.label("person_id"),
            people.c.display_name.label("display_name"),
            faces.c.face_id.label("matched_face_id"),
            distance_expression.label("distance"),
            func.row_number()
            .over(
                partition_by=faces.c.person_id,
                order_by=(distance_expression.asc(), faces.c.face_id.asc()),
            )
            .label("person_rank"),
        )
        .select_from(faces.join(people, faces.c.person_id == people.c.person_id))
        .where(
            faces.c.face_id != face_id,
            faces.c.person_id.is_not(None),
            faces.c.embedding.is_not(None),
        )
        .subquery()
    )

    rows = (
        connection.execute(
            select(
                ranked_candidates.c.person_id,
                ranked_candidates.c.display_name,
                ranked_candidates.c.matched_face_id,
                ranked_candidates.c.distance,
            )
            .where(ranked_candidates.c.person_rank == 1)
            .order_by(ranked_candidates.c.distance.asc(), ranked_candidates.c.person_id.asc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    return [
        {
            "person_id": str(row["person_id"]),
            "display_name": str(row["display_name"]),
            "matched_face_id": str(row["matched_face_id"]),
            "distance": float(row["distance"]),
        }
        for row in rows
    ]


def _lookup_candidates_python(
    connection: Connection,
    *,
    face_id: str,
    source_embedding: list[float],
) -> list[dict[str, object]]:
    candidate_rows = (
        connection.execute(
            select(
                faces.c.face_id,
                faces.c.person_id,
                faces.c.embedding,
                people.c.display_name,
            )
            .select_from(faces.join(people, faces.c.person_id == people.c.person_id))
            .where(
                faces.c.face_id != face_id,
                faces.c.person_id.is_not(None),
                faces.c.embedding.is_not(None),
            )
        )
        .mappings()
        .all()
    )

    best_by_person: dict[str, dict[str, object]] = {}
    for row in candidate_rows:
        candidate_embedding = _coerce_embedding(row["embedding"])
        if candidate_embedding is None:
            continue
        if len(candidate_embedding) != len(source_embedding):
            continue

        distance = _cosine_distance(source_embedding, candidate_embedding)
        if distance is None:
            continue

        person_id = str(row["person_id"])
        best_candidate = best_by_person.get(person_id)
        if best_candidate is None or distance < float(best_candidate["distance"]):
            best_by_person[person_id] = {
                "person_id": person_id,
                "display_name": str(row["display_name"]),
                "matched_face_id": str(row["face_id"]),
                "distance": distance,
            }

    return sorted(
        best_by_person.values(),
        key=lambda item: (float(item["distance"]), str(item["person_id"])),
    )


def _with_candidate_confidence(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for candidate in candidates:
        distance = float(candidate["distance"])
        enriched = dict(candidate)
        enriched["confidence"] = distance_to_confidence(distance)
        results.append(enriched)
    return results


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
    left_norm = sqrt(sum(component * component for component in left))
    right_norm = sqrt(sum(component * component for component in right))
    if left_norm == 0 or right_norm == 0:
        return None

    dot_product = sum(left_component * right_component for left_component, right_component in zip(left, right))
    similarity = dot_product / (left_norm * right_norm)
    bounded_similarity = min(1.0, max(-1.0, similarity))
    return 1.0 - bounded_similarity
