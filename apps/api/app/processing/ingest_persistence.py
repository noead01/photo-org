from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.engine import Connection

from app.path_contract import build_rooted_photo_path, relative_photo_path
from app.processing.metadata import extract_image_metadata, stat_timestamp_to_iso
from app.storage import faces, photos


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
    thumbnail_jpeg: bytes | None = None
    thumbnail_mime_type: str | None = None
    thumbnail_width: int | None = None
    thumbnail_height: int | None = None
    faces_count: int = 0


def build_photo_record(path: Path, *, canonical_path: str) -> PhotoRecord:
    stat = path.stat()
    image_metadata = extract_image_metadata(path)
    sha256 = _sha256_file(path)
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
    )


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


def upsert_photo(connection: Connection, record: PhotoRecord) -> bool:
    existing = connection.execute(
        select(
            photos.c.photo_id,
            photos.c.thumbnail_jpeg,
            photos.c.thumbnail_mime_type,
            photos.c.thumbnail_width,
            photos.c.thumbnail_height,
        ).where(photos.c.path == record.path)
    ).mappings().first()

    payload = _photo_row_payload(
        record,
        thumbnail_fields=_coalesce_thumbnail_fields(record, existing),
        faces_count=record.faces_count,
        faces_detected_ts=None,
    )

    if existing is None:
        _insert_photo_row(connection, payload)
        return True

    _update_photo_row(connection, photos.c.path == record.path, payload)
    return False


def upsert_source_photo(connection: Connection, record: PhotoRecord) -> tuple[bool, str]:
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
            faces_detected_ts=_sqlite_timestamp_sql(datetime.now(tz=UTC)),
        )
    )


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
        "faces_count": record.faces_count,
    }


def _photo_row_payload(
    record: PhotoRecord,
    *,
    photo_id: str | None = None,
    thumbnail_fields: dict[str, object | None],
    faces_count: int,
    faces_detected_ts: datetime | None,
) -> dict[str, object | None]:
    payload = {
        **asdict(record),
        "photo_id": photo_id or record.photo_id,
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
        "embedding": _json_safe_embedding(detection.get("embedding")),
        "provenance": detection.get("provenance", {}),
    }


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
    connection.execute(insert(photos).values(**_sqlite_timestamp_payload(connection, payload)))


def _update_photo_row(
    connection: Connection,
    where_clause,
    payload: dict[str, object | None],
) -> None:
    connection.execute(
        update(photos)
        .where(where_clause)
        .values(**_sqlite_timestamp_payload(connection, payload))
    )


def _sqlite_timestamp_payload(
    connection: Connection,
    payload: dict[str, object | None],
) -> dict[str, object | None]:
    if connection.dialect.name != "sqlite":
        return payload

    converted = dict(payload)
    for column_name in _PHOTO_TIMESTAMP_COLUMNS:
        value = converted.get(column_name)
        if isinstance(value, datetime):
            converted[column_name] = _sqlite_timestamp_sql(value)
    return converted


def _sqlite_timestamp_sql(value: datetime):
    return text(f"'{_normalize_timestamp(value).isoformat(sep=' ')}'")


def _json_safe_embedding(value: object) -> object:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return list(bytes(value))
    return value


__all__ = [
    "PhotoRecord",
    "build_ingest_submission",
    "build_photo_record",
    "store_face_detections",
    "upsert_photo",
    "upsert_source_photo",
]


_PHOTO_TIMESTAMP_COLUMNS = (
    "created_ts",
    "modified_ts",
    "shot_ts",
    "updated_ts",
    "faces_detected_ts",
)
