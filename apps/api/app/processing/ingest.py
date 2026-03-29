from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from stat import S_ISDIR
from typing import Iterable, Protocol
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection

from app.db.config import resolve_missing_file_grace_period_days
from app.db.ingest_runs import IngestRunStore
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
from app.services.source_registration import SourceRegistrationError, read_source_marker
from app.services.thumbnails import generate_thumbnail
from app.storage import create_db_engine, faces, photos, storage_source_aliases, watched_folders


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
    thumbnail_jpeg: bytes | None = None
    thumbnail_mime_type: str | None = None
    thumbnail_width: int | None = None
    thumbnail_height: int | None = None
    faces_count: int = 0


@dataclass
class IngestResult:
    scanned: int = 0
    enqueued: int = 0
    inserted: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RegisteredWatchedFolderTarget:
    storage_source_id: str
    watched_folder_id: str
    container_mount_path: str
    relative_path: str | None


@dataclass(frozen=True)
class RegisteredStorageSourceTarget:
    storage_source_id: str
    alias_paths: tuple[str, ...]
    watched_folders: tuple[RegisteredWatchedFolderTarget, ...]


@dataclass(frozen=True)
class WatchedFolderPollOutcome:
    scanned: int
    inserted: int
    updated: int
    error_messages: tuple[str, ...]
    status: str


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

    engine = create_db_engine(database_url)
    with engine.begin() as connection:
        watched_folder_id = ensure_watched_folder_exists(
            connection,
            scan_path=source_root.as_posix(),
            container_mount_path=canonical_root,
            now=at,
        )
        outcome = _reconcile_watched_folder_root(
            connection,
            watched_folder_id=watched_folder_id,
            source_root=source_root,
            canonical_root=canonical_root,
            now=at,
            missing_file_grace_period_days=grace_period_days,
        )
        result.scanned += outcome.scanned
        result.inserted += outcome.inserted
        result.updated += outcome.updated
        result.errors.extend(outcome.error_messages)

    return result


def poll_registered_storage_sources(
    database_url: str | Path | None = None,
    *,
    now: datetime | None = None,
    missing_file_grace_period_days: int | None = None,
) -> IngestResult:
    result = IngestResult()
    at = now if now is not None else utc_now()
    grace_period_days = resolve_missing_file_grace_period_days(missing_file_grace_period_days)
    engine = create_db_engine(database_url)
    run_store = IngestRunStore(database_url)

    with engine.begin() as connection:
        targets = _load_registered_storage_source_targets(connection)

    for source_target in targets:
        reason, detail, alias_root = _validate_registered_source_target(
            storage_source_id=source_target.storage_source_id,
            alias_paths=source_target.alias_paths,
        )
        if reason is not None:
            with engine.begin() as connection:
                for target in source_target.watched_folders:
                    record_watched_folder_scan_failure(
                        connection,
                        watched_folder_id=target.watched_folder_id,
                        reason=reason,
                        now=at,
                    )
                    _record_ingest_run(
                        run_store,
                        connection=connection,
                        watched_folder_id=target.watched_folder_id,
                        status="failed",
                        files_seen=0,
                        files_created=0,
                        files_updated=0,
                        error_messages=(detail,),
                    )
            result.errors.append(f"storage_source:{source_target.storage_source_id}: {detail}")
            continue

        with engine.begin() as connection:
            for target in source_target.watched_folders:
                scan_root = _resolve_registered_scan_root(
                    alias_root=alias_root,
                    relative_path=target.relative_path,
                )
                outcome = _reconcile_watched_folder_root(
                    connection,
                    watched_folder_id=target.watched_folder_id,
                    source_root=scan_root,
                    canonical_root=target.container_mount_path,
                    now=at,
                    missing_file_grace_period_days=grace_period_days,
                )
                result.scanned += outcome.scanned
                result.inserted += outcome.inserted
                result.updated += outcome.updated
                result.errors.extend(outcome.error_messages)
                _record_ingest_run(
                    run_store,
                    connection=connection,
                    watched_folder_id=target.watched_folder_id,
                    status=outcome.status,
                    files_seen=outcome.scanned,
                    files_created=outcome.inserted,
                    files_updated=outcome.updated,
                    error_messages=outcome.error_messages,
                )

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


def _reconcile_watched_folder_root(
    connection: Connection,
    *,
    watched_folder_id: str,
    source_root: Path,
    canonical_root: str,
    now: datetime,
    missing_file_grace_period_days: int,
) -> WatchedFolderPollOutcome:
    scanned = 0
    inserted = 0
    updated_count = 0
    error_messages: list[str] = []
    try:
        _validate_scan_root(source_root)
        scanned_paths = list(iter_photo_files(source_root))
    except OSError as exc:
        record_watched_folder_scan_failure(
            connection,
            watched_folder_id=watched_folder_id,
            reason=_classify_root_scan_failure(exc),
            now=now,
        )
        return WatchedFolderPollOutcome(
            scanned=0,
            inserted=0,
            updated=0,
            error_messages=(),
            status="failed",
        )

    record_watched_folder_scan_success(
        connection,
        watched_folder_id=watched_folder_id,
        now=now,
    )
    observed_relative_paths: set[str] = set()
    touched_photo_ids: set[str] = set()

    for photo_path in scanned_paths:
        scanned += 1
        relative_path = relative_photo_path(source_root, photo_path)
        record = build_photo_record(
            photo_path,
            canonical_path=build_canonical_photo_path(canonical_root, relative_path),
        )
        try:
            thumbnail = generate_thumbnail(photo_path)
        except Exception as exc:
            error_messages.append(f"{photo_path}: thumbnail generation failed: {exc}")
        else:
            record = PhotoRecord(
                **{
                    **record.__dict__,
                    "thumbnail_jpeg": thumbnail.jpeg_bytes,
                    "thumbnail_mime_type": thumbnail.mime_type,
                    "thumbnail_width": thumbnail.width,
                    "thumbnail_height": thumbnail.height,
                }
            )
        observed_relative_paths.add(relative_path)
        created = upsert_photo(connection, record)
        if created:
            inserted += 1
        else:
            updated_count += 1
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
                now=now,
            )
        )

    touched_photo_ids.update(
        reconcile_watched_folder(
            connection,
            watched_folder_id=watched_folder_id,
            observed_relative_paths=observed_relative_paths,
            now=now,
            missing_file_grace_period_days=missing_file_grace_period_days,
        )
    )
    refresh_photo_deleted_timestamps(connection, photo_ids=touched_photo_ids, now=now)
    return WatchedFolderPollOutcome(
        scanned=scanned,
        inserted=inserted,
        updated=updated_count,
        error_messages=tuple(error_messages),
        status="completed",
    )


def _load_registered_storage_source_targets(
    connection: Connection,
) -> list[RegisteredStorageSourceTarget]:
    aliases_by_source: dict[str, list[str]] = {}
    for row in connection.execute(
        select(
            storage_source_aliases.c.storage_source_id,
            storage_source_aliases.c.alias_path,
        ).order_by(
            storage_source_aliases.c.storage_source_id,
            storage_source_aliases.c.alias_path,
        )
    ).mappings():
        aliases_by_source.setdefault(row["storage_source_id"], []).append(row["alias_path"])

    watched_folders_by_source: dict[str, list[RegisteredWatchedFolderTarget]] = {}
    for row in connection.execute(
        select(
            watched_folders.c.storage_source_id,
            watched_folders.c.watched_folder_id,
            watched_folders.c.container_mount_path,
            watched_folders.c.relative_path,
        )
        .where(
            watched_folders.c.is_enabled == 1,
            watched_folders.c.storage_source_id.is_not(None),
        )
        .order_by(
            watched_folders.c.storage_source_id,
            watched_folders.c.relative_path,
            watched_folders.c.watched_folder_id,
        )
    ).mappings():
        watched_folders_by_source.setdefault(row["storage_source_id"], []).append(
            RegisteredWatchedFolderTarget(
                storage_source_id=row["storage_source_id"],
                watched_folder_id=row["watched_folder_id"],
                container_mount_path=row["container_mount_path"],
                relative_path=row["relative_path"],
            )
        )

    return [
        RegisteredStorageSourceTarget(
            storage_source_id=storage_source_id,
            alias_paths=tuple(aliases_by_source.get(storage_source_id, [])),
            watched_folders=tuple(source_watched_folders),
        )
        for storage_source_id, source_watched_folders in watched_folders_by_source.items()
    ]


def _validate_registered_source_target(
    *,
    storage_source_id: str,
    alias_paths: tuple[str, ...],
) -> tuple[str | None, str | None, Path | None]:
    if not alias_paths:
        return "alias_missing", "no registered alias is available for polling", None

    first_failure: tuple[str, str] | None = None
    for alias_path in alias_paths:
        alias_root = Path(alias_path).expanduser().resolve()
        try:
            _validate_scan_root(alias_root)
            marker = read_source_marker(alias_root)
        except OSError as exc:
            failure = (_classify_source_failure(exc), _describe_source_failure(exc))
        except SourceRegistrationError as exc:
            failure = ("marker_invalid", str(exc))
        else:
            if marker is None:
                failure = ("marker_missing", "storage source marker file is missing")
            elif str(marker["storage_source_id"]) != storage_source_id:
                failure = ("marker_mismatch", "marker file does not match expected storage source")
            else:
                return None, None, alias_root
        if first_failure is None:
            first_failure = failure

    assert first_failure is not None
    return first_failure[0], first_failure[1], None


def _resolve_registered_scan_root(*, alias_root: Path, relative_path: str | None) -> Path:
    if relative_path in {None, "."}:
        return alias_root
    return alias_root / relative_path


def _classify_source_failure(exc: OSError) -> str:
    if isinstance(exc, PermissionError):
        return "source_permission_denied"
    if isinstance(exc, (FileNotFoundError, NotADirectoryError)):
        return "source_unreachable"
    return "source_io_error"


def _describe_source_failure(exc: OSError) -> str:
    if isinstance(exc, PermissionError):
        return "storage source root is not readable"
    if isinstance(exc, (FileNotFoundError, NotADirectoryError)):
        return "storage source root is unavailable"
    return f"storage source validation failed: {exc}"


def _record_ingest_run(
    run_store: IngestRunStore,
    *,
    connection: Connection,
    watched_folder_id: str,
    status: str,
    files_seen: int,
    files_created: int,
    files_updated: int,
    error_messages: tuple[str, ...],
) -> None:
    ingest_run_id = run_store.create_run(
        watched_folder_id=watched_folder_id,
        connection=connection,
    )
    run_store.finalize_run(
        ingest_run_id,
        status=status,
        files_seen=files_seen,
        files_created=files_created,
        files_updated=files_updated,
        error_count=len(error_messages),
        error_summary=_error_summary(error_messages),
        connection=connection,
    )


def _error_summary(error_messages: tuple[str, ...]) -> str | None:
    if not error_messages:
        return None
    return error_messages[0]


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
    ).mappings().first()

    thumbnail_jpeg = record.thumbnail_jpeg
    thumbnail_mime_type = record.thumbnail_mime_type
    thumbnail_width = record.thumbnail_width
    thumbnail_height = record.thumbnail_height
    if (
        existing is not None
        and thumbnail_jpeg is None
        and thumbnail_mime_type is None
        and thumbnail_width is None
        and thumbnail_height is None
    ):
        existing_thumbnail = connection.execute(
            select(
                photos.c.thumbnail_jpeg,
                photos.c.thumbnail_mime_type,
                photos.c.thumbnail_width,
                photos.c.thumbnail_height,
            ).where(photos.c.path == record.path)
        ).mappings().one()
        thumbnail_jpeg = existing_thumbnail["thumbnail_jpeg"]
        thumbnail_mime_type = existing_thumbnail["thumbnail_mime_type"]
        thumbnail_width = existing_thumbnail["thumbnail_width"]
        thumbnail_height = existing_thumbnail["thumbnail_height"]

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
        "thumbnail_jpeg": thumbnail_jpeg,
        "thumbnail_mime_type": thumbnail_mime_type,
        "thumbnail_width": thumbnail_width,
        "thumbnail_height": thumbnail_height,
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
