from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection

from app.path_contract import build_rooted_photo_path, relative_photo_path
from app.processing.metadata import extract_image_metadata, stat_timestamp_to_iso
from app.storage import exif_semantic_mappings, faces, photo_exif_attributes, photos
from photoorg_db_schema import EMBEDDING_DIMENSION


@dataclass(frozen=True)
class PhotoRecord:
    photo_id: str
    path: str
    sha256: str
    filesize: int
    ext: str
    created_ts: datetime
    modified_ts: datetime
    shot_ts: datetime | None
    shot_ts_source: str | None
    camera_make: str | None
    camera_model: str | None
    software: str | None
    orientation: str | None
    gps_latitude: float | None
    gps_longitude: float | None
    gps_altitude: float | None
    exif_attributes: dict[str, Any] | None = None
    exif_unmapped_attributes: dict[str, Any] | None = None
    thumbnail_jpeg: bytes | None = None
    thumbnail_mime_type: str | None = None
    thumbnail_width: int | None = None
    thumbnail_height: int | None = None
    faces_count: int = 0


def build_photo_record(path: Path, *, canonical_path: str) -> PhotoRecord:
    stat = path.stat()
    image_metadata = extract_image_metadata(path)
    sha256 = _sha256_file(path)
    return build_photo_record_from_sha(
        path,
        canonical_path=canonical_path,
        sha256=sha256,
        stat=stat,
        image_metadata=image_metadata,
    )


def build_photo_record_from_sha(
    path: Path,
    *,
    canonical_path: str,
    sha256: str,
    stat=None,
    image_metadata=None,
) -> PhotoRecord:
    stat = stat or path.stat()
    image_metadata = image_metadata or extract_image_metadata(path)
    photo_id = str(uuid5(NAMESPACE_URL, f"{canonical_path}:{sha256}"))

    return PhotoRecord(
        photo_id=photo_id,
        path=canonical_path,
        sha256=sha256,
        filesize=stat.st_size,
        ext=path.suffix.lower().lstrip("."),
        created_ts=_parse_timestamp(stat_timestamp_to_iso(stat.st_ctime)),
        modified_ts=_parse_timestamp(stat_timestamp_to_iso(stat.st_mtime)),
        shot_ts=_parse_timestamp(image_metadata.shot_ts),
        shot_ts_source=image_metadata.shot_ts_source,
        camera_make=image_metadata.camera_make,
        camera_model=image_metadata.camera_model,
        software=image_metadata.software,
        orientation=image_metadata.orientation,
        gps_latitude=image_metadata.gps_latitude,
        gps_longitude=image_metadata.gps_longitude,
        gps_altitude=image_metadata.gps_altitude,
        exif_attributes=image_metadata.exif_attributes,
        exif_unmapped_attributes=image_metadata.exif_unmapped_attributes,
    )


def compute_photo_sha256(path: Path) -> str:
    return _sha256_file(path)


def build_ingest_submission(
    path: Path,
    *,
    scan_root: Path,
    path_root: str | Path,
) -> dict:
    relative_path = relative_photo_path(scan_root, path)
    record = build_photo_record(
        path,
        canonical_path=build_rooted_photo_path(path_root, relative_path),
    )
    payload = _serialize_record(record)
    payload["idempotency_key"] = record.photo_id
    return payload


def build_ingest_candidate_submission(
    path: Path,
    *,
    scan_root: Path,
    canonical_path: str,
    storage_source_id: str,
    watched_folder_id: str,
) -> dict:
    relative_path = relative_photo_path(scan_root, path)
    stat = path.stat()
    modified_ts = _normalize_timestamp(_parse_timestamp(stat_timestamp_to_iso(stat.st_mtime))).isoformat()
    return {
        "payload_version": 1,
        "storage_source_id": storage_source_id,
        "watched_folder_id": watched_folder_id,
        "canonical_path": canonical_path,
        "runtime_path": str(path.resolve()),
        "relative_path": relative_path,
        "filesize": stat.st_size,
        "modified_ts": modified_ts,
        "modified_mtime_ns": stat.st_mtime_ns,
        "idempotency_key": f"{watched_folder_id}:{relative_path}:{stat.st_size}:{stat.st_mtime_ns}",
    }


def serialize_extracted_content_submission(
    *,
    record: PhotoRecord,
    storage_source_id: str,
    watched_folder_id: str,
    relative_path: str,
    detections: list[dict],
    warnings: list[str],
) -> dict:
    payload = _serialize_record(record)
    payload.update(
        {
            "payload_version": 1,
            "storage_source_id": storage_source_id,
            "watched_folder_id": watched_folder_id,
            "relative_path": relative_path,
            "detections": _serialize_detections(detections),
            "warnings": warnings,
        }
    )
    return payload


def serialize_reused_content_submission(
    *,
    record: PhotoRecord,
    candidate_payload: dict,
    warnings: list[str],
    detections: list[dict] | None = None,
) -> dict:
    payload = _serialize_record(record)
    payload.update(
        {
            "payload_version": 1,
            "storage_source_id": candidate_payload["storage_source_id"],
            "watched_folder_id": candidate_payload["watched_folder_id"],
            "relative_path": candidate_payload["relative_path"],
            "detections": _serialize_detections(detections or []),
            "warnings": warnings,
        }
    )
    return payload


def lookup_existing_artifacts_by_sha(
    connection: Connection,
    sha256: str,
) -> dict[str, object | None] | None:
    rows = connection.execute(
        select(
            photos.c.photo_id,
            photos.c.shot_ts,
            photos.c.shot_ts_source,
            photos.c.camera_make,
            photos.c.camera_model,
            photos.c.software,
            photos.c.orientation,
            photos.c.gps_latitude,
            photos.c.gps_longitude,
            photos.c.gps_altitude,
            photos.c.thumbnail_jpeg,
            photos.c.thumbnail_mime_type,
            photos.c.thumbnail_width,
            photos.c.thumbnail_height,
            photos.c.faces_count,
            photos.c.faces_detected_ts,
        ).where(photos.c.sha256 == sha256)
    ).mappings().all()

    for row in sorted(rows, key=_sha_reuse_sort_key):
        reusable = _build_reusable_artifacts_payload(connection, row)
        if reusable is not None:
            return reusable

    return None


def upsert_photo(connection: Connection, record: PhotoRecord) -> bool:
    record = _with_semantic_shot_fields(connection, record)
    existing = connection.execute(
        select(photos.c.photo_id).where(photos.c.path == record.path)
    ).mappings().first()

    existing_thumbnail_fields = existing
    if existing is not None and _thumbnail_fields_missing(record):
        existing_thumbnail_fields = connection.execute(
            select(
                photos.c.thumbnail_jpeg,
                photos.c.thumbnail_mime_type,
                photos.c.thumbnail_width,
                photos.c.thumbnail_height,
            ).where(photos.c.path == record.path)
        ).mappings().one()

    payload = _photo_row_payload(
        record,
        thumbnail_fields=_coalesce_thumbnail_fields(record, existing_thumbnail_fields),
        faces_count=record.faces_count,
        faces_detected_ts=None,
    )

    if existing is None:
        _insert_photo_row(connection, payload)
        _sync_photo_exif_attributes(connection, record.photo_id, record.exif_attributes)
        return True

    _update_photo_row(connection, photos.c.path == record.path, payload)
    _sync_photo_exif_attributes(connection, record.photo_id, record.exif_attributes)
    return False


def upsert_source_photo(connection: Connection, record: PhotoRecord) -> tuple[bool, str]:
    record = _with_semantic_shot_fields(connection, record)
    existing = connection.execute(
        select(
            photos.c.photo_id,
            photos.c.thumbnail_jpeg,
            photos.c.thumbnail_mime_type,
            photos.c.thumbnail_width,
            photos.c.thumbnail_height,
            photos.c.faces_count,
            photos.c.faces_detected_ts,
        ).where(photos.c.sha256 == record.sha256)
    ).mappings().first()

    if existing is not None:
        _update_photo_row(
            connection,
            photos.c.photo_id == existing["photo_id"],
            _photo_row_payload(
                record,
                photo_id=existing["photo_id"],
                thumbnail_fields=_coalesce_thumbnail_fields(record, existing),
                faces_count=existing["faces_count"],
                faces_detected_ts=_normalize_optional_timestamp(existing["faces_detected_ts"]),
            ),
        )
        _sync_photo_exif_attributes(connection, existing["photo_id"], record.exif_attributes)
        return False, existing["photo_id"]

    _insert_photo_row(
        connection,
        _photo_row_payload(
            record,
            thumbnail_fields=_coalesce_thumbnail_fields(record, None),
            faces_count=record.faces_count,
            faces_detected_ts=None,
        ),
    )
    _sync_photo_exif_attributes(connection, record.photo_id, record.exif_attributes)
    return True, record.photo_id


def store_face_detections(connection: Connection, photo_id: str, detections: list[dict]) -> None:
    connection.execute(delete(faces).where(faces.c.photo_id == photo_id))
    for detection in detections:
        connection.execute(insert(faces).values(**_face_row(photo_id, detection)))

    connection.execute(
        update(photos)
        .where(photos.c.photo_id == photo_id)
        .values(
            faces_count=len(detections),
            faces_detected_ts=datetime.now(tz=UTC),
        )
    )


def deserialize_photo_record(payload: dict) -> PhotoRecord:
    return PhotoRecord(
        photo_id=payload["photo_id"],
        path=payload["path"],
        sha256=payload["sha256"],
        filesize=payload["filesize"],
        ext=payload["ext"],
        created_ts=_parse_timestamp(payload["created_ts"]),
        modified_ts=_parse_timestamp(payload["modified_ts"]),
        shot_ts=_parse_timestamp(payload.get("shot_ts")),
        shot_ts_source=payload.get("shot_ts_source"),
        camera_make=payload.get("camera_make"),
        camera_model=payload.get("camera_model"),
        software=payload.get("software"),
        orientation=payload.get("orientation"),
        gps_latitude=payload.get("gps_latitude"),
        gps_longitude=payload.get("gps_longitude"),
        gps_altitude=payload.get("gps_altitude"),
        exif_attributes=payload.get("exif_attributes"),
        exif_unmapped_attributes=payload.get("exif_unmapped_attributes"),
        thumbnail_jpeg=_decode_optional_bytes(payload.get("thumbnail_jpeg")),
        thumbnail_mime_type=payload.get("thumbnail_mime_type"),
        thumbnail_width=payload.get("thumbnail_width"),
        thumbnail_height=payload.get("thumbnail_height"),
        faces_count=payload.get("faces_count", 0),
    )


def deserialize_detections(payload: list[dict] | None) -> list[dict]:
    return [
        {
            **detection,
            "bitmap": _decode_optional_bytes(detection.get("bitmap")),
            "embedding": _normalize_embedding(detection.get("embedding")),
        }
        for detection in (payload or [])
    ]


def _serialize_record(record: PhotoRecord) -> dict:
    return {
        "photo_id": record.photo_id,
        "path": record.path,
        "sha256": record.sha256,
        "filesize": record.filesize,
        "ext": record.ext,
        "created_ts": record.created_ts.isoformat(),
        "modified_ts": record.modified_ts.isoformat(),
        "shot_ts": _format_optional_timestamp(record.shot_ts),
        "shot_ts_source": record.shot_ts_source,
        "camera_make": record.camera_make,
        "camera_model": record.camera_model,
        "software": record.software,
        "orientation": record.orientation,
        "gps_latitude": record.gps_latitude,
        "gps_longitude": record.gps_longitude,
        "gps_altitude": record.gps_altitude,
        "exif_attributes": record.exif_attributes,
        "exif_unmapped_attributes": record.exif_unmapped_attributes,
        "thumbnail_jpeg": _encode_optional_thumbnail(record.thumbnail_jpeg),
        "thumbnail_mime_type": record.thumbnail_mime_type,
        "thumbnail_width": record.thumbnail_width,
        "thumbnail_height": record.thumbnail_height,
        "faces_count": record.faces_count,
    }


def _serialize_detections(detections: list[dict]) -> list[dict]:
    return [
        {
            **detection,
            "bitmap": _encode_optional_bytes(detection.get("bitmap")),
            "embedding": _normalize_embedding(detection.get("embedding")),
        }
        for detection in detections
    ]


def _photo_row_payload(
    record: PhotoRecord,
    *,
    photo_id: str | None = None,
    thumbnail_fields: dict[str, object | None],
    faces_count: int,
    faces_detected_ts: datetime | None,
) -> dict[str, object | None]:
    payload = {
        "photo_id": photo_id or record.photo_id,
        "path": record.path,
        "sha256": record.sha256,
        "filesize": record.filesize,
        "ext": record.ext,
        "shot_ts_source": record.shot_ts_source,
        "camera_make": record.camera_make,
        "camera_model": record.camera_model,
        "software": record.software,
        "orientation": record.orientation,
        "gps_latitude": record.gps_latitude,
        "gps_longitude": record.gps_longitude,
        "gps_altitude": record.gps_altitude,
        "phash": None,
        "created_ts": _normalize_timestamp(record.created_ts),
        "modified_ts": _normalize_timestamp(record.modified_ts),
        "shot_ts": _normalize_optional_timestamp(record.shot_ts),
        "updated_ts": _normalize_timestamp(record.modified_ts),
        "faces_count": faces_count,
        "faces_detected_ts": _normalize_optional_timestamp(faces_detected_ts),
    }
    payload.update(thumbnail_fields)
    return payload


def _coalesce_thumbnail_fields(
    record: PhotoRecord,
    existing: object,
) -> dict[str, object | None]:
    thumbnail_fields = _thumbnail_fields(record)
    if existing is None or any(value is not None for value in thumbnail_fields.values()):
        return thumbnail_fields

    return {
        "thumbnail_jpeg": existing["thumbnail_jpeg"],
        "thumbnail_mime_type": existing["thumbnail_mime_type"],
        "thumbnail_width": existing["thumbnail_width"],
        "thumbnail_height": existing["thumbnail_height"],
    }


def _thumbnail_fields(record: PhotoRecord) -> dict[str, object | None]:
    return {
        "thumbnail_jpeg": record.thumbnail_jpeg,
        "thumbnail_mime_type": record.thumbnail_mime_type,
        "thumbnail_width": record.thumbnail_width,
        "thumbnail_height": record.thumbnail_height,
    }


def _thumbnail_fields_missing(record: PhotoRecord) -> bool:
    return all(value is None for value in _thumbnail_fields(record).values())


def _face_row(photo_id: str, detection: dict) -> dict[str, object]:
    return {
        "face_id": detection["face_id"],
        "photo_id": photo_id,
        "person_id": detection.get("person_id"),
        "bbox_x": detection.get("bbox_x"),
        "bbox_y": detection.get("bbox_y"),
        "bbox_w": detection.get("bbox_w"),
        "bbox_h": detection.get("bbox_h"),
        "bitmap": detection.get("bitmap"),
        "embedding": _normalize_optional_embedding(detection),
        "provenance": detection.get("provenance", {}),
    }


def _build_reusable_artifacts_payload(
    connection: Connection,
    row: dict[str, object | None],
) -> dict[str, object | None] | None:
    if (
        row["thumbnail_jpeg"] is None
        or row["thumbnail_mime_type"] is None
        or row["thumbnail_width"] is None
        or row["thumbnail_height"] is None
        or row["faces_detected_ts"] is None
    ):
        return None

    detections = connection.execute(
        select(
            faces.c.face_id,
            faces.c.person_id,
            faces.c.bbox_x,
            faces.c.bbox_y,
            faces.c.bbox_w,
            faces.c.bbox_h,
            faces.c.bitmap,
            faces.c.embedding,
            faces.c.provenance,
        )
        .where(faces.c.photo_id == row["photo_id"])
        .order_by(faces.c.face_id)
    ).mappings().all()

    if int(row["faces_count"] or 0) != len(detections):
        return None

    exif_attribute_rows = connection.execute(
        select(
            photo_exif_attributes.c.exif_attribute_name,
            photo_exif_attributes.c.exif_attribute_value,
        )
        .where(photo_exif_attributes.c.photo_id == row["photo_id"])
        .order_by(photo_exif_attributes.c.exif_attribute_name)
    ).mappings().all()
    exif_attributes = {
        str(attribute_row["exif_attribute_name"]): attribute_row["exif_attribute_value"]
        for attribute_row in exif_attribute_rows
    }

    return {
        "photo_id": row["photo_id"],
        "shot_ts": row["shot_ts"],
        "shot_ts_source": row["shot_ts_source"],
        "camera_make": row["camera_make"],
        "camera_model": row["camera_model"],
        "software": row["software"],
        "orientation": row["orientation"],
        "gps_latitude": row["gps_latitude"],
        "gps_longitude": row["gps_longitude"],
        "gps_altitude": row["gps_altitude"],
        "exif_attributes": exif_attributes or None,
        "exif_unmapped_attributes": None,
        "thumbnail_jpeg": row["thumbnail_jpeg"],
        "thumbnail_mime_type": row["thumbnail_mime_type"],
        "thumbnail_width": row["thumbnail_width"],
        "thumbnail_height": row["thumbnail_height"],
        "faces_count": int(row["faces_count"] or 0),
        "faces_detected_ts": row["faces_detected_ts"],
        "detections": [dict(detection) for detection in detections],
    }


def _sha_reuse_sort_key(row: dict[str, object | None]) -> tuple[int, int, str]:
    thumbnail_complete = all(
        row[column] is not None
        for column in (
            "thumbnail_jpeg",
            "thumbnail_mime_type",
            "thumbnail_width",
            "thumbnail_height",
        )
    )
    faces_complete = row["faces_detected_ts"] is not None
    metadata_score = sum(
        1
        for column in (
            "shot_ts",
            "shot_ts_source",
            "camera_make",
            "camera_model",
            "software",
            "orientation",
            "gps_latitude",
            "gps_longitude",
            "gps_altitude",
        )
        if row.get(column) is not None
    )
    return (
        0 if thumbnail_complete and faces_complete else 1,
        -metadata_score,
        str(row["photo_id"]),
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _encode_optional_bytes(value: bytes | None) -> str | None:
    if value is None:
        return None
    return base64.b64encode(value).decode("ascii")


def _encode_optional_thumbnail(value: bytes | None) -> str | None:
    return _encode_optional_bytes(value)


def _decode_optional_bytes(value: str | None) -> bytes | None:
    if value is None:
        return None
    return base64.b64decode(value)


def _normalize_embedding(value: object) -> list[float] | None:
    if value is None:
        return None

    if hasattr(value, "tolist"):
        value = value.tolist()

    if not isinstance(value, list | tuple):
        raise ValueError("face embedding must be a list-like sequence of floats")

    embedding = [float(component) for component in value]
    if len(embedding) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"face embedding dimension must be {EMBEDDING_DIMENSION}, got {len(embedding)}"
        )
    return embedding


def _normalize_optional_embedding(detection: dict) -> list[float] | None:
    return _normalize_embedding(detection.get("embedding"))


def _format_optional_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_optional_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _normalize_timestamp(value)


def _insert_photo_row(connection: Connection, payload: dict[str, object | None]) -> None:
    connection.execute(insert(photos).values(**payload))


def _update_photo_row(
    connection: Connection,
    where_clause,
    payload: dict[str, object | None],
) -> None:
    connection.execute(
        update(photos)
        .where(where_clause)
        .values(**payload)
    )


def _with_semantic_shot_fields(connection: Connection, record: PhotoRecord) -> PhotoRecord:
    resolved_shot_ts, resolved_source = _resolve_semantic_shot_fields(connection, record.exif_attributes)
    if resolved_shot_ts is None:
        return record
    return replace(
        record,
        shot_ts=resolved_shot_ts,
        shot_ts_source=resolved_source or record.shot_ts_source,
    )


def _resolve_semantic_shot_fields(
    connection: Connection,
    exif_attributes: dict[str, Any] | None,
) -> tuple[datetime | None, str | None]:
    if not exif_attributes:
        return None, None

    raw_datetime, datetime_attr_name = _first_semantic_attribute_value(
        connection,
        semantic_key="shot_datetime",
        exif_attributes=exif_attributes,
    )
    if raw_datetime is None:
        return None, None

    parsed = _parse_exif_datetime(str(raw_datetime).strip())
    if parsed is None:
        return None, None

    raw_subsec, _ = _first_semantic_attribute_value(
        connection,
        semantic_key="shot_subsec",
        exif_attributes=exif_attributes,
    )
    if raw_subsec is not None:
        digits = "".join(ch for ch in str(raw_subsec) if ch.isdigit())[:6]
        if digits:
            parsed = parsed.replace(microsecond=int(digits.ljust(6, "0")))

    raw_offset, _ = _first_semantic_attribute_value(
        connection,
        semantic_key="shot_offset",
        exif_attributes=exif_attributes,
    )
    if raw_offset is not None:
        offset_text = str(raw_offset).strip()
        if _valid_offset(offset_text):
            offset_hours = int(offset_text[1:3])
            offset_minutes = int(offset_text[4:6])
            offset_delta = timedelta(hours=offset_hours, minutes=offset_minutes)
            if offset_text[0] == "-":
                offset_delta = -offset_delta
            return parsed.replace(tzinfo=timezone(offset_delta)), _shot_source_label(datetime_attr_name)

    return parsed.replace(tzinfo=UTC), _shot_source_label(datetime_attr_name)


def _first_semantic_attribute_value(
    connection: Connection,
    *,
    semantic_key: str,
    exif_attributes: dict[str, Any],
) -> tuple[Any | None, str | None]:
    rows = connection.execute(
        select(exif_semantic_mappings.c.exif_attribute_name)
        .where(exif_semantic_mappings.c.semantic_key == semantic_key)
        .order_by(exif_semantic_mappings.c.precedence.asc(), exif_semantic_mappings.c.exif_attribute_name.asc())
    ).scalars().all()
    for attribute_name in rows:
        value = exif_attributes.get(attribute_name)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        return value, str(attribute_name)
    return None, None


def _parse_exif_datetime(value: str) -> datetime | None:
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _valid_offset(value: str) -> bool:
    if len(value) != 6:
        return False
    if value[0] not in {"+", "-"}:
        return False
    return value[1:3].isdigit() and value[3] == ":" and value[4:6].isdigit()


def _shot_source_label(attribute_name: str | None) -> str | None:
    if attribute_name is None:
        return None
    if attribute_name.startswith("exif_ifd.") or attribute_name.startswith("exif."):
        namespace, tag_name = attribute_name.split(".", 1)
        return f"{namespace}:{tag_name}"
    return f"exif_attr:{attribute_name}"


def _sync_photo_exif_attributes(
    connection: Connection,
    photo_id: str,
    exif_attributes: dict[str, Any] | None,
) -> None:
    connection.execute(delete(photo_exif_attributes).where(photo_exif_attributes.c.photo_id == photo_id))
    if not exif_attributes:
        return

    for attribute_name, attribute_value in sorted(exif_attributes.items()):
        connection.execute(
            insert(photo_exif_attributes).values(
                photo_id=photo_id,
                exif_attribute_name=attribute_name,
                exif_attribute_value=attribute_value,
            )
        )


__all__ = [
    "PhotoRecord",
    "build_ingest_candidate_submission",
    "build_ingest_submission",
    "build_photo_record",
    "build_photo_record_from_sha",
    "compute_photo_sha256",
    "deserialize_detections",
    "deserialize_photo_record",
    "lookup_existing_artifacts_by_sha",
    "serialize_extracted_content_submission",
    "serialize_reused_content_submission",
    "store_face_detections",
    "upsert_photo",
    "upsert_source_photo",
]
