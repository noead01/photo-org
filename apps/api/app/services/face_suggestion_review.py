from __future__ import annotations

from math import ceil

from sqlalchemy import case, func, select
from sqlalchemy.engine import Connection

from app.services.face_assignment import (
    FaceAlreadyAssignedError,
    FaceNotFoundError,
    PersonNotFoundError,
    assign_face_to_person,
)
from app.services.face_candidates import lookup_nearest_neighbor_candidates
from app.storage import face_suggestions, faces, people, photo_exif_attributes, photos


SUGGESTION_SKIP_FACE_NOT_FOUND = "face_not_found"
SUGGESTION_SKIP_ALREADY_ASSIGNED = "already_assigned"
SUGGESTION_SKIP_NO_TOP_SUGGESTION = "no_top_suggestion"
SUGGESTION_SKIP_SUGGESTED_PERSON_NOT_FOUND = "suggested_person_not_found"


def _top_suggestion_subquery():
    ranked = (
        select(
            face_suggestions.c.face_id.label("face_id"),
            face_suggestions.c.person_id.label("person_id"),
            face_suggestions.c.confidence.label("confidence"),
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
    return (
        select(
            ranked.c.face_id,
            ranked.c.person_id,
            ranked.c.confidence,
        )
        .where(ranked.c.suggestion_rank == 1)
        .subquery()
    )


def _extract_bbox_space_dimensions(face_provenance: object) -> tuple[int | None, int | None]:
    if not isinstance(face_provenance, dict):
        return None, None
    width = _coerce_positive_int(face_provenance.get("bbox_space_width"))
    height = _coerce_positive_int(face_provenance.get("bbox_space_height"))
    return width, height


def _coerce_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        coerced = int(value)
        return coerced if coerced > 0 else None
    if isinstance(value, str):
        try:
            coerced = int(value.strip())
        except ValueError:
            return None
        return coerced if coerced > 0 else None
    return None


def _load_photo_dimension_map(
    connection: Connection,
    *,
    photo_ids: list[str],
) -> dict[str, tuple[int | None, int | None]]:
    if not photo_ids:
        return {}
    dimension_attrs = {
        "exif_ifd.exifimagewidth": "width",
        "exif_ifd.exifimageheight": "height",
        "exif_ifd.pixelxdimension": "width",
        "exif_ifd.pixelydimension": "height",
        "exif.imagewidth": "width",
        "exif.imagelength": "height",
    }
    rows = (
        connection.execute(
            select(
                photo_exif_attributes.c.photo_id,
                photo_exif_attributes.c.exif_attribute_name,
                photo_exif_attributes.c.exif_attribute_value,
            ).where(photo_exif_attributes.c.photo_id.in_(photo_ids))
        )
        .mappings()
        .all()
    )
    dimensions: dict[str, dict[str, int | None]] = {}
    for row in rows:
        photo_id = str(row["photo_id"])
        key = str(row["exif_attribute_name"]).lower()
        axis = dimension_attrs.get(key)
        if axis is None:
            continue
        value = _coerce_positive_int(row["exif_attribute_value"])
        if value is None:
            continue
        current = dimensions.setdefault(photo_id, {"width": None, "height": None})
        # Keep the largest candidate for each axis; EXIF can repeat across namespaces.
        existing = current[axis]
        current[axis] = max(existing or 0, value)

    return {
        photo_id: (values.get("width"), values.get("height"))
        for photo_id, values in dimensions.items()
    }


def _load_live_top_candidate_for_face(
    connection: Connection,
    *,
    face_id: str,
) -> dict[str, object] | None:
    result = lookup_nearest_neighbor_candidates(
        connection,
        face_id=face_id,
        limit=1,
        enforce_min_confidence=False,
    )
    candidates = result.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    top = candidates[0]
    person_id = top.get("person_id")
    display_name = top.get("display_name")
    confidence = top.get("confidence")
    if not isinstance(person_id, str) or not person_id:
        return None
    if not isinstance(display_name, str) or not display_name:
        return None
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        return None
    return {
        "person_id": person_id,
        "display_name": display_name,
        "confidence": min(1.0, max(0.0, confidence_value)),
    }


def list_unassigned_face_suggestion_photos(
    connection: Connection,
    *,
    page: int,
    page_size: int,
    min_confidence: float = 0.0,
) -> dict[str, object]:
    normalized_min_confidence = min(1.0, max(0.0, float(min_confidence)))
    top_suggestion = _top_suggestion_subquery()
    eligible_photo_ids = (
        select(faces.c.photo_id)
        .select_from(
            faces.join(top_suggestion, top_suggestion.c.face_id == faces.c.face_id).join(
                photos, photos.c.photo_id == faces.c.photo_id
            )
        )
        .where(
            faces.c.person_id.is_(None),
            faces.c.dismissed_ts.is_(None),
            photos.c.deleted_ts.is_(None),
            top_suggestion.c.confidence >= normalized_min_confidence,
        )
        .distinct()
        .subquery()
    )

    total_items = int(
        connection.execute(select(func.count()).select_from(eligible_photo_ids)).scalar_one()
    )
    total_pages = ceil(total_items / page_size) if total_items > 0 else 0

    photo_rows = (
        connection.execute(
            select(
                photos.c.photo_id,
                photos.c.path,
                photos.c.thumbnail_jpeg,
                photos.c.thumbnail_mime_type,
                photos.c.thumbnail_width,
                photos.c.thumbnail_height,
                photos.c.shot_ts,
            )
            .select_from(
                photos.join(eligible_photo_ids, eligible_photo_ids.c.photo_id == photos.c.photo_id)
            )
            .order_by(
                case((photos.c.shot_ts.is_(None), 1), else_=0).asc(),
                photos.c.shot_ts.desc(),
                photos.c.photo_id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .mappings()
        .all()
    )
    photo_ids = [str(row["photo_id"]) for row in photo_rows]
    if not photo_ids:
        return {
            "page": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
            },
            "items": [],
        }

    face_rows = (
        connection.execute(
            select(
                faces.c.photo_id,
                faces.c.face_id,
                faces.c.bbox_x,
                faces.c.bbox_y,
                faces.c.bbox_w,
                faces.c.bbox_h,
                faces.c.provenance,
                top_suggestion.c.person_id.label("suggested_person_id"),
                top_suggestion.c.confidence.label("suggested_confidence"),
                people.c.display_name.label("suggested_display_name"),
            )
            .select_from(
                faces.join(top_suggestion, top_suggestion.c.face_id == faces.c.face_id).join(
                    people, people.c.person_id == top_suggestion.c.person_id
                )
            )
            .where(
                faces.c.photo_id.in_(photo_ids),
                faces.c.person_id.is_(None),
                faces.c.dismissed_ts.is_(None),
                top_suggestion.c.confidence >= normalized_min_confidence,
            )
            .order_by(
                faces.c.photo_id.asc(),
                faces.c.face_id.asc(),
            )
        )
        .mappings()
        .all()
    )
    photo_dimension_map = _load_photo_dimension_map(connection, photo_ids=photo_ids)

    face_map: dict[str, list[dict[str, object]]] = {photo_id: [] for photo_id in photo_ids}
    for row in face_rows:
        photo_id = str(row["photo_id"])
        bbox_space_width, bbox_space_height = _extract_bbox_space_dimensions(row["provenance"])
        if bbox_space_width is None or bbox_space_height is None:
            fallback_width, fallback_height = photo_dimension_map.get(photo_id, (None, None))
            bbox_space_width = bbox_space_width or fallback_width
            bbox_space_height = bbox_space_height or fallback_height
        top_suggestion_payload = {
            "person_id": str(row["suggested_person_id"]),
            "display_name": str(row["suggested_display_name"]),
            "confidence": float(row["suggested_confidence"]),
        }
        live_top_candidate = _load_live_top_candidate_for_face(
            connection,
            face_id=str(row["face_id"]),
        )
        if live_top_candidate is not None:
            top_suggestion_payload = live_top_candidate
        face_map.setdefault(photo_id, []).append(
            {
                "face_id": str(row["face_id"]),
                "bbox_x": row["bbox_x"],
                "bbox_y": row["bbox_y"],
                "bbox_w": row["bbox_w"],
                "bbox_h": row["bbox_h"],
                "bbox_space_width": bbox_space_width,
                "bbox_space_height": bbox_space_height,
                "top_suggestion": top_suggestion_payload,
            }
        )

    items: list[dict[str, object]] = []
    for row in photo_rows:
        thumbnail = None
        thumbnail_jpeg = row["thumbnail_jpeg"]
        thumbnail_mime_type = row["thumbnail_mime_type"]
        thumbnail_width = row["thumbnail_width"]
        thumbnail_height = row["thumbnail_height"]
        if thumbnail_jpeg and thumbnail_mime_type and thumbnail_width and thumbnail_height:
            import base64

            thumbnail = {
                "mime_type": thumbnail_mime_type,
                "width": int(thumbnail_width),
                "height": int(thumbnail_height),
                "data_base64": base64.b64encode(thumbnail_jpeg).decode("ascii"),
            }

        photo_id = str(row["photo_id"])
        suggestions_for_photo = face_map.get(photo_id, [])
        if not suggestions_for_photo:
            continue
        items.append(
            {
                "photo_id": photo_id,
                "path": str(row["path"]),
                "thumbnail": thumbnail,
                "faces": suggestions_for_photo,
            }
        )

    return {
        "page": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        },
        "items": items,
    }


def confirm_top_face_suggestions(
    connection: Connection,
    *,
    face_ids: list[str],
) -> dict[str, object]:
    assigned: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    seen: set[str] = set()
    unique_face_ids = [face_id for face_id in face_ids if face_id and not (face_id in seen or seen.add(face_id))]

    for face_id in unique_face_ids:
        face_row = (
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
        if face_row is None:
            skipped.append({"face_id": face_id, "reason": SUGGESTION_SKIP_FACE_NOT_FOUND})
            continue

        if face_row["person_id"] is not None:
            skipped.append({"face_id": face_id, "reason": SUGGESTION_SKIP_ALREADY_ASSIGNED})
            continue

        top_suggestion_row = (
            connection.execute(
                select(face_suggestions.c.person_id)
                .where(face_suggestions.c.face_id == face_id)
                .order_by(
                    face_suggestions.c.rank.asc(),
                    face_suggestions.c.confidence.desc(),
                    face_suggestions.c.person_id.asc(),
                )
                .limit(1)
            )
            .mappings()
            .first()
        )
        if top_suggestion_row is None:
            skipped.append({"face_id": face_id, "reason": SUGGESTION_SKIP_NO_TOP_SUGGESTION})
            continue

        suggested_person_id = str(top_suggestion_row["person_id"])
        try:
            assignment = assign_face_to_person(
                connection,
                face_id=face_id,
                person_id=suggested_person_id,
            )
            assigned.append(
                {
                    "face_id": str(assignment["face_id"]),
                    "photo_id": str(assignment["photo_id"]),
                    "person_id": str(assignment["person_id"]),
                }
            )
        except FaceNotFoundError:
            skipped.append({"face_id": face_id, "reason": SUGGESTION_SKIP_FACE_NOT_FOUND})
        except FaceAlreadyAssignedError:
            skipped.append({"face_id": face_id, "reason": SUGGESTION_SKIP_ALREADY_ASSIGNED})
        except PersonNotFoundError:
            skipped.append(
                {"face_id": face_id, "reason": SUGGESTION_SKIP_SUGGESTED_PERSON_NOT_FOUND}
            )

    return {
        "assigned": assigned,
        "skipped": skipped,
    }
