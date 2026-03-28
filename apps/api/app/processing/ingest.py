from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from dataclasses import dataclass, field
from pathlib import Path
from stat import S_ISDIR
from typing import Iterable, Protocol
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Connection

from app.db.config import resolve_missing_file_grace_period_days
from app.db.queue import IngestQueueStore
from app.path_contract import (
    build_canonical_photo_path,
    normalize_container_mount_path,
    relative_photo_path,
)
from app.services.file_reconciliation import (
    activate_observed_file,
    ensure_watched_folder_exists,
    record_watched_folder_scan_failure,
    record_watched_folder_scan_success,
    refresh_photo_deleted_timestamps,
    reconcile_watched_folder,
    utc_now,
)
from app.processing.metadata import extract_image_metadata, stat_timestamp_to_iso
from app.storage import create_db_engine, faces, photos


SUPPORTED_EXTENSIONS = {".heic", ".heif", ".jpeg", ".jpg", ".png"}


class FaceDetector(Protocol):
    def detect(self, path: Path) -> list[dict]:
        """Return face detections for a photo."""


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
    faces_count: int = 0


@dataclass
class IngestResult:
    scanned: int = 0
    enqueued: int = 0
    inserted: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)


def ingest_directory(
    root: str | Path,
    database_url: str | Path | None = None,
    *,
    container_mount_path: str | Path | None = None,
    face_detector: FaceDetector | None = None,
) -> IngestResult:
    source_root = Path(root).expanduser().resolve()
    canonical_root = normalize_container_mount_path(container_mount_path or source_root)
    result = IngestResult()

    queue_store = IngestQueueStore(database_url)

    for photo_path in iter_photo_files(source_root):
        result.scanned += 1
        try:
            payload = build_ingest_submission(
                photo_path,
                scan_root=source_root,
                container_mount_path=canonical_root,
            )
            queue_store.enqueue(
                payload_type="photo_metadata",
                payload=payload,
                idempotency_key=payload["idempotency_key"],
            )
            result.enqueued += 1
        except Exception as exc:
            result.errors.append(f"{photo_path}: {exc}")

    return result


def reconcile_directory(
    root: str | Path,
    database_url: str | Path | None = None,
    *,
    container_mount_path: str | Path | None = None,
    now: datetime | None = None,
    missing_file_grace_period_days: int | None = None,
) -> IngestResult:
    source_root = Path(root).expanduser().resolve()
    canonical_root = normalize_container_mount_path(container_mount_path or source_root)
    result = IngestResult()
    at = now if now is not None else utc_now()
    grace_period_days = resolve_missing_file_grace_period_days(missing_file_grace_period_days)

    try:
        _validate_scan_root(source_root)
        scanned_paths = list(iter_photo_files(source_root))
    except OSError as exc:
        engine = create_db_engine(database_url)
        with engine.begin() as connection:
            watched_folder_id = ensure_watched_folder_exists(
                connection,
                scan_path=source_root.as_posix(),
                container_mount_path=canonical_root,
                now=at,
            )
            record_watched_folder_scan_failure(
                connection,
                watched_folder_id=watched_folder_id,
                reason=_classify_root_scan_failure(exc),
                now=at,
            )
        return result

    engine = create_db_engine(database_url)
    with engine.begin() as connection:
        watched_folder_id = ensure_watched_folder_exists(
            connection,
            scan_path=source_root.as_posix(),
            container_mount_path=canonical_root,
            now=at,
        )
        record_watched_folder_scan_success(
            connection,
            watched_folder_id=watched_folder_id,
            now=at,
        )
        observed_relative_paths: set[str] = set()
        touched_photo_ids: set[str] = set()

        for photo_path in scanned_paths:
            result.scanned += 1
            relative_path = relative_photo_path(source_root, photo_path)
            record = build_photo_record(
                photo_path,
                canonical_path=build_canonical_photo_path(canonical_root, relative_path),
            )
            observed_relative_paths.add(relative_path)
            created = upsert_photo(connection, record)
            if created:
                result.inserted += 1
            else:
                result.updated += 1
            touched_photo_ids.add(
                activate_observed_file(
                    connection,
                    watched_folder_id=watched_folder_id,
                    photo_id=record.photo_id,
                    relative_path=relative_path,
                    filename=photo_path.name,
                    extension=record.ext,
                    filesize=record.filesize,
                    created_ts=record.created_ts,
                    modified_ts=record.modified_ts,
                    now=at,
                )
            )

        touched_photo_ids.update(
            reconcile_watched_folder(
                connection,
                watched_folder_id=watched_folder_id,
                observed_relative_paths=observed_relative_paths,
                now=at,
                missing_file_grace_period_days=grace_period_days,
            )
        )
        refresh_photo_deleted_timestamps(connection, photo_ids=touched_photo_ids, now=at)

    return result


def _validate_scan_root(root: Path) -> None:
    if not S_ISDIR(root.stat().st_mode):
        raise NotADirectoryError(str(root))


def _classify_root_scan_failure(exc: OSError) -> str:
    if isinstance(exc, PermissionError):
        return "permission_denied"
    if isinstance(exc, (FileNotFoundError, NotADirectoryError)):
        return "folder_unmounted"
    return "io_error"


def iter_photo_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path
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
    container_mount_path: str | Path,
) -> dict:
    relative_path = relative_photo_path(scan_root, path)
    record = build_photo_record(
        path,
        canonical_path=build_canonical_photo_path(container_mount_path, relative_path),
    )
    payload = {
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
    payload["idempotency_key"] = record.photo_id
    return payload


def upsert_photo(connection: Connection, record: PhotoRecord) -> bool:
    existing = connection.execute(
        select(photos.c.photo_id).where(photos.c.path == record.path)
    ).first()

    payload = {
        "photo_id": record.photo_id,
        "path": record.path,
        "sha256": record.sha256,
        "phash": None,
        "filesize": record.filesize,
        "ext": record.ext,
        "created_ts": record.created_ts,
        "modified_ts": record.modified_ts,
        "shot_ts": record.shot_ts,
        "shot_ts_source": record.shot_ts_source,
        "camera_make": record.camera_make,
        "camera_model": record.camera_model,
        "software": record.software,
        "orientation": record.orientation,
        "gps_latitude": record.gps_latitude,
        "gps_longitude": record.gps_longitude,
        "gps_altitude": record.gps_altitude,
        "updated_ts": record.modified_ts,
        "faces_count": record.faces_count,
        "faces_detected_ts": None,
    }

    if existing is None:
        connection.execute(insert(photos).values(**payload))
        return True

    connection.execute(
        update(photos)
        .where(photos.c.path == record.path)
        .values(**payload)
    )
    return False


def store_face_detections(connection: Connection, photo_id: str, detections: list[dict]) -> None:
    connection.execute(delete(faces).where(faces.c.photo_id == photo_id))
    for detection in detections:
        connection.execute(
            insert(faces).values(
                face_id=detection["face_id"],
                photo_id=photo_id,
                person_id=detection.get("person_id"),
                bbox_x=detection.get("bbox_x"),
                bbox_y=detection.get("bbox_y"),
                bbox_w=detection.get("bbox_w"),
                bbox_h=detection.get("bbox_h"),
                bitmap=detection.get("bitmap"),
                embedding=detection.get("embedding"),
                provenance=detection.get("provenance", {}),
            )
        )

    connection.execute(
        update(photos)
        .where(photos.c.photo_id == photo_id)
        .values(
            faces_count=len(detections),
            faces_detected_ts=datetime.now(tz=UTC),
        )
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


def _format_optional_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
