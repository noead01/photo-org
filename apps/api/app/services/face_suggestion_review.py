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
from app.services.people import UNKNOWN_PERSON_DISPLAY_NAME
from app.storage import face_suggestions, faces, people, photo_exif_attributes, photos


SUGGESTION_SKIP_FACE_NOT_FOUND = "face_not_found"
SUGGESTION_SKIP_ALREADY_ASSIGNED = "already_assigned"
SUGGESTION_SKIP_NO_TOP_SUGGESTION = "no_top_suggestion"
SUGGESTION_SKIP_SUGGESTED_PERSON_NOT_FOUND = "suggested_person_not_found"
SUGGESTION_SKIP_SELECTED_PERSON_NOT_SUGGESTED = "selected_person_not_suggested"


def _top_suggestion_subquery(*, excluded_person_ids: set[str]):
    ranked = select(
        face_suggestions.c.face_id.label("face_id"),
        face_suggestions.c.person_id.label("person_id"),
        people.c.display_name.label("display_name"),
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
    ).select_from(
        face_suggestions.join(
            people,
            face_suggestions.c.person_id == people.c.person_id,
        )
    ).where(people.c.display_name != UNKNOWN_PERSON_DISPLAY_NAME)
    if excluded_person_ids:
        ranked = ranked.where(~face_suggestions.c.person_id.in_(sorted(excluded_person_ids)))
    ranked = ranked.subquery()
    return (
        select(
            ranked.c.face_id,
            ranked.c.person_id,
            ranked.c.display_name,
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


def list_unassigned_face_suggestion_photos(
    connection: Connection,
    *,
    page: int,
    page_size: int,
    min_confidence: float = 0.0,
    excluded_person_ids: list[str] | None = None,
) -> dict[str, object]:
    normalized_min_confidence = min(1.0, max(0.0, float(min_confidence)))
    normalized_excluded_person_ids = {
        person_id.strip()
        for person_id in (excluded_person_ids or [])
        if isinstance(person_id, str) and person_id.strip()
    }
    top_suggestion = _top_suggestion_subquery(
        excluded_person_ids=normalized_excluded_person_ids,
    )
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
                top_suggestion.c.display_name.label("suggested_display_name"),
            )
            .select_from(
                faces.join(top_suggestion, top_suggestion.c.face_id == faces.c.face_id)
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
    face_ids = [str(row["face_id"]) for row in face_rows]
    suggestion_rows = (
        connection.execute(
            select(
                face_suggestions.c.face_id,
                face_suggestions.c.person_id,
                people.c.display_name,
                face_suggestions.c.rank,
                face_suggestions.c.confidence,
            )
            .select_from(
                face_suggestions.join(
                    people,
                    face_suggestions.c.person_id == people.c.person_id,
                )
            )
            .where(
                face_suggestions.c.face_id.in_(face_ids),
                people.c.display_name != UNKNOWN_PERSON_DISPLAY_NAME,
            )
            .order_by(
                face_suggestions.c.face_id.asc(),
                face_suggestions.c.rank.asc(),
                face_suggestions.c.confidence.desc(),
                face_suggestions.c.person_id.asc(),
            )
        )
        .mappings()
        .all()
    )
    suggestions_by_face_id: dict[str, list[dict[str, object]]] = {}
    for row in suggestion_rows:
        person_id = str(row["person_id"])
        if person_id in normalized_excluded_person_ids:
            continue
        face_id = str(row["face_id"])
        suggestions_by_face_id.setdefault(face_id, []).append(
            {
                "person_id": person_id,
                "display_name": str(row["display_name"]),
                "confidence": float(row["confidence"]),
                "rank": int(row["rank"]),
            }
        )

    face_map: dict[str, list[dict[str, object]]] = {photo_id: [] for photo_id in photo_ids}
    for row in face_rows:
        photo_id = str(row["photo_id"])
        bbox_space_width, bbox_space_height = _extract_bbox_space_dimensions(row["provenance"])
        if bbox_space_width is None or bbox_space_height is None:
            fallback_width, fallback_height = photo_dimension_map.get(photo_id, (None, None))
            bbox_space_width = bbox_space_width or fallback_width
            bbox_space_height = bbox_space_height or fallback_height
        face_id = str(row["face_id"])
        suggestions = suggestions_by_face_id.get(face_id, [])
        if not suggestions:
            top_suggestion_payload = {
                "person_id": str(row["suggested_person_id"]),
                "display_name": str(row["suggested_display_name"]),
                "confidence": float(row["suggested_confidence"]),
            }
            suggestions = [top_suggestion_payload]
        top_suggestion_payload = suggestions[0]
        face_map.setdefault(photo_id, []).append(
            {
                "face_id": face_id,
                "bbox_x": row["bbox_x"],
                "bbox_y": row["bbox_y"],
                "bbox_w": row["bbox_w"],
                "bbox_h": row["bbox_h"],
                "bbox_space_width": bbox_space_width,
                "bbox_space_height": bbox_space_height,
                "top_suggestion": top_suggestion_payload,
                "suggestions": suggestions,
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
    selected_assignments: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    assigned: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    explicit_assignments: dict[str, str] = {}
    for assignment in selected_assignments or []:
        raw_face_id = assignment.get("face_id")
        raw_person_id = assignment.get("person_id")
        if not isinstance(raw_face_id, str) or not raw_face_id.strip():
            continue
        if not isinstance(raw_person_id, str) or not raw_person_id.strip():
            continue
        explicit_assignments[raw_face_id.strip()] = raw_person_id.strip()

    seen: set[str] = set()
    unique_face_ids: list[str] = []
    for face_id in list(explicit_assignments.keys()) + face_ids:
        if not isinstance(face_id, str):
            continue
        normalized_face_id = face_id.strip()
        if not normalized_face_id or normalized_face_id in seen:
            continue
        seen.add(normalized_face_id)
        unique_face_ids.append(normalized_face_id)

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

        suggestion_rows = (
            connection.execute(
                select(face_suggestions.c.person_id)
                .select_from(
                    face_suggestions.join(
                        people,
                        face_suggestions.c.person_id == people.c.person_id,
                    )
                )
                .where(face_suggestions.c.face_id == face_id)
                .where(people.c.display_name != UNKNOWN_PERSON_DISPLAY_NAME)
                .order_by(
                    face_suggestions.c.rank.asc(),
                    face_suggestions.c.confidence.desc(),
                    face_suggestions.c.person_id.asc(),
                )
            )
            .mappings()
            .all()
        )
        if not suggestion_rows:
            skipped.append({"face_id": face_id, "reason": SUGGESTION_SKIP_NO_TOP_SUGGESTION})
            continue

        suggested_person_ids = [str(row["person_id"]) for row in suggestion_rows]
        selected_person_id = explicit_assignments.get(face_id)
        if selected_person_id is None:
            suggested_person_id = suggested_person_ids[0]
        elif selected_person_id not in suggested_person_ids:
            skipped.append(
                {
                    "face_id": face_id,
                    "reason": SUGGESTION_SKIP_SELECTED_PERSON_NOT_SUGGESTED,
                }
            )
            continue
        else:
            suggested_person_id = selected_person_id

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
