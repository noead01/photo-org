from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import sqrt
from uuid import uuid4

from sqlalchemy import delete, func, insert, select
from sqlalchemy.engine import Connection

from photoorg_db_schema import FACE_LABEL_SOURCE_HUMAN_CONFIRMED

from app.services.face_candidates import lookup_nearest_neighbor_candidates
from app.services.recognition_policy import resolve_prediction_metadata
from app.storage import face_labels, face_suggestions, faces, person_representations


SCORING_VERSION = "hybrid-v1"
LIVE_SCORING_VERSION = "nearest-neighbor-live-v1"


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


@dataclass(frozen=True)
class StaleUnassignedRefreshResult:
    stale_after_minutes: int
    suggestion_limit: int
    requested_face_limit: int
    refreshed_face_count: int
    stale_cutoff_ts: datetime


def persist_face_suggestions_from_live_candidates(
    connection: Connection,
    *,
    face_id: str,
    candidates: list[dict[str, object]],
    model_version: str,
    limit: int = 5,
) -> int:
    source_row = (
        connection.execute(
            select(faces.c.face_id, faces.c.person_id).where(faces.c.face_id == face_id)
        )
        .mappings()
        .first()
    )
    if source_row is None:
        return 0
    if source_row["person_id"] is not None:
        _delete_face_suggestions(connection, face_id=face_id)
        return 0

    normalized_candidates: list[dict[str, object]] = []
    for candidate in candidates[: max(0, limit)]:
        person_id = candidate.get("person_id")
        if not isinstance(person_id, str) or not person_id:
            continue
        confidence = candidate.get("confidence")
        distance = candidate.get("distance")
        try:
            confidence_value = float(confidence)
            distance_value = float(distance) if distance is not None else None
        except (TypeError, ValueError):
            continue
        normalized_candidates.append(
            {
                "person_id": person_id,
                "confidence": min(1.0, max(0.0, confidence_value)),
                "distance": distance_value,
                "matched_face_id": (
                    str(candidate.get("matched_face_id"))
                    if candidate.get("matched_face_id") is not None
                    else None
                ),
            }
        )

    _delete_face_suggestions(connection, face_id=face_id)
    for rank, candidate in enumerate(normalized_candidates, start=1):
        connection.execute(
            insert(face_suggestions).values(
                face_suggestion_id=str(uuid4()),
                face_id=face_id,
                person_id=candidate["person_id"],
                rank=rank,
                confidence=candidate["confidence"],
                centroid_distance=candidate["distance"],
                knn_distance=candidate["distance"],
                representation_version=1,
                scoring_version=LIVE_SCORING_VERSION,
                model_version=model_version,
                provenance={
                    "source": "live-candidate-lookup",
                    "matched_face_id": candidate["matched_face_id"],
                    "distance": candidate["distance"],
                },
            )
        )
    return len(normalized_candidates)


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


def refresh_face_suggestions_for_people_in_top_rank(
    connection: Connection,
    *,
    person_ids: list[str],
    top_rank_cutoff: int = 3,
    limit: int = 5,
) -> int:
    normalized_person_ids = sorted({person_id for person_id in person_ids if person_id})
    if not normalized_person_ids:
        return 0
    if top_rank_cutoff < 1:
        return 0

    ranked_suggestions = (
        select(
            face_suggestions.c.face_id.label("face_id"),
            face_suggestions.c.person_id.label("person_id"),
            func.row_number()
            .over(
                partition_by=face_suggestions.c.face_id,
                order_by=(
                    face_suggestions.c.rank.asc(),
                    face_suggestions.c.confidence.desc(),
                    face_suggestions.c.person_id.asc(),
                ),
            )
            .label("suggestion_rank"),
        )
        .subquery()
    )
    target_face_rows = (
        connection.execute(
            select(ranked_suggestions.c.face_id)
            .select_from(
                ranked_suggestions.join(
                    faces,
                    faces.c.face_id == ranked_suggestions.c.face_id,
                )
            )
            .where(
                ranked_suggestions.c.suggestion_rank <= top_rank_cutoff,
                ranked_suggestions.c.person_id.in_(normalized_person_ids),
                faces.c.person_id.is_(None),
                faces.c.embedding.is_not(None),
            )
            .distinct()
            .order_by(ranked_suggestions.c.face_id.asc())
        )
        .scalars()
        .all()
    )

    for face_id in target_face_rows:
        refresh_face_suggestions_for_face(
            connection,
            face_id=str(face_id),
            limit=limit,
        )
    return len(target_face_rows)


def refresh_stale_unassigned_face_suggestions(
    connection: Connection,
    *,
    stale_after_minutes: int,
    face_limit: int,
    suggestion_limit: int = 5,
) -> StaleUnassignedRefreshResult:
    normalized_stale_after_minutes = max(0, stale_after_minutes)
    normalized_face_limit = max(0, face_limit)
    normalized_suggestion_limit = max(1, suggestion_limit)
    stale_cutoff_ts = datetime.now(tz=UTC) - timedelta(
        minutes=normalized_stale_after_minutes
    )

    if normalized_face_limit == 0:
        return StaleUnassignedRefreshResult(
            stale_after_minutes=normalized_stale_after_minutes,
            suggestion_limit=normalized_suggestion_limit,
            requested_face_limit=0,
            refreshed_face_count=0,
            stale_cutoff_ts=stale_cutoff_ts,
        )

    latest_suggestion_snapshot = (
        select(
            face_suggestions.c.face_id.label("face_id"),
            func.max(face_suggestions.c.updated_ts).label("last_suggestion_ts"),
        )
        .group_by(face_suggestions.c.face_id)
        .subquery()
    )

    target_face_ids = (
        connection.execute(
            select(faces.c.face_id)
            .select_from(
                faces.outerjoin(
                    latest_suggestion_snapshot,
                    latest_suggestion_snapshot.c.face_id == faces.c.face_id,
                )
            )
            .where(
                faces.c.person_id.is_(None),
                faces.c.embedding.is_not(None),
                (
                    latest_suggestion_snapshot.c.face_id.is_(None)
                    | (
                        latest_suggestion_snapshot.c.last_suggestion_ts
                        <= stale_cutoff_ts
                    )
                ),
            )
            .order_by(faces.c.face_id.asc())
            .limit(normalized_face_limit)
        )
        .scalars()
        .all()
    )

    for face_id in target_face_ids:
        refresh_face_suggestions_for_face(
            connection,
            face_id=str(face_id),
            limit=normalized_suggestion_limit,
        )

    return StaleUnassignedRefreshResult(
        stale_after_minutes=normalized_stale_after_minutes,
        suggestion_limit=normalized_suggestion_limit,
        requested_face_limit=normalized_face_limit,
        refreshed_face_count=len(target_face_ids),
        stale_cutoff_ts=stale_cutoff_ts,
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
    result = lookup_nearest_neighbor_candidates(
        connection,
        face_id=face_id,
        limit=limit,
        enforce_min_confidence=False,
    )
    candidates = result.get("candidates")
    if not isinstance(candidates, list):
        candidates = []
    model_version = resolve_prediction_metadata()["model_version"]
    persist_face_suggestions_from_live_candidates(
        connection,
        face_id=face_id,
        candidates=candidates,
        model_version=model_version,
        limit=limit,
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
