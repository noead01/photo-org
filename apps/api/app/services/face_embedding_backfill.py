from __future__ import annotations

import io
import os
from typing import Any

from PIL import Image, UnidentifiedImageError
from sqlalchemy import or_, select, update
from sqlalchemy.engine import Connection

from app.processing.faces import (
    FACE_RECOGNITION_SFACE_MODEL_FILE_ENV,
    OpenCvSFaceEmbeddingExtractor,
)
from app.services.face_suggestions import refresh_face_suggestions_for_person_scope
from app.services.person_representations import refresh_person_representation
from app.storage import faces


class FaceEmbeddingModelUnavailableError(RuntimeError):
    pass


def reembed_missing_face_embeddings(
    connection: Connection,
    *,
    limit: int = 1000,
    refresh_related: bool = True,
    suggestion_limit: int = 5,
) -> dict[str, int]:
    extractor = _build_extractor()

    rows = (
        connection.execute(
            select(
                faces.c.face_id,
                faces.c.person_id,
                faces.c.bitmap,
            )
            .where(_missing_embedding_predicate(connection))
            .order_by(faces.c.face_id.asc())
            .limit(limit)
        )
        .mappings()
        .all()
    )

    scanned = len(rows)
    updated_count = 0
    skipped_missing_bitmap = 0
    skipped_extraction_failed = 0
    impacted_person_ids: set[str] = set()

    for row in rows:
        face_id = str(row["face_id"])
        bitmap = _coerce_bitmap_bytes(row["bitmap"])
        if bitmap is None:
            skipped_missing_bitmap += 1
            continue

        embedding = _extract_embedding(bitmap, extractor)
        if embedding is None:
            skipped_extraction_failed += 1
            continue

        connection.execute(
            update(faces)
            .where(faces.c.face_id == face_id)
            .values(embedding=embedding)
        )
        updated_count += 1
        person_id = row["person_id"]
        if person_id is not None:
            impacted_person_ids.add(str(person_id))

    refreshed_people = 0
    refreshed_suggestion_scopes = 0
    if refresh_related:
        for person_id in sorted(impacted_person_ids):
            refresh_person_representation(connection, person_id=person_id)
            refreshed_people += 1
            refresh_face_suggestions_for_person_scope(
                connection,
                person_id=person_id,
                limit=suggestion_limit,
            )
            refreshed_suggestion_scopes += 1

    return {
        "scanned": scanned,
        "updated": updated_count,
        "skipped_missing_bitmap": skipped_missing_bitmap,
        "skipped_extraction_failed": skipped_extraction_failed,
        "refreshed_people": refreshed_people,
        "refreshed_suggestion_scopes": refreshed_suggestion_scopes,
    }


def _build_extractor() -> OpenCvSFaceEmbeddingExtractor:
    model_path = os.getenv(FACE_RECOGNITION_SFACE_MODEL_FILE_ENV, "").strip()
    if not model_path:
        raise FaceEmbeddingModelUnavailableError(
            f"{FACE_RECOGNITION_SFACE_MODEL_FILE_ENV} is not configured"
        )
    try:
        return OpenCvSFaceEmbeddingExtractor(model_path)
    except FileNotFoundError as exc:
        raise FaceEmbeddingModelUnavailableError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive guard around model init
        raise FaceEmbeddingModelUnavailableError(
            f"failed to initialize SFace embedding extractor: {exc}"
        ) from exc


def _coerce_bitmap_bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value if value else None
    if isinstance(value, memoryview):
        coerced = value.tobytes()
        return coerced if coerced else None
    return None


def _extract_embedding(
    bitmap: bytes,
    extractor: OpenCvSFaceEmbeddingExtractor,
) -> list[float] | None:
    try:
        with Image.open(io.BytesIO(bitmap)) as image:
            return extractor.extract(image)
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _missing_embedding_predicate(connection: Connection):
    if connection.dialect.name == "sqlite":
        # SQLite JSON columns may persist Python None as JSON literal "null".
        return or_(faces.c.embedding.is_(None), faces.c.embedding == "null")
    return faces.c.embedding.is_(None)
