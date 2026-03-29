from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from stat import S_ISDIR
from typing import Callable, Iterable

from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.db.config import resolve_missing_file_grace_period_days
from app.db.ingest_runs import IngestRunStore
from app.path_contract import build_rooted_photo_path, build_source_aware_photo_path, relative_photo_path
from app.processing.ingest_persistence import (
    PhotoRecord,
    build_photo_record,
    upsert_photo,
    upsert_source_photo,
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
from app.services.source_registration import SourceRegistrationError, read_source_marker
from app.services.thumbnails import generate_thumbnail
from app.storage import create_db_engine, storage_source_aliases, watched_folders


SUPPORTED_EXTENSIONS = {".heic", ".heif", ".jpeg", ".jpg", ".png"}


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


def reconcile_directory(
    root: str | Path,
    database_url: str | Path | None = None,
    *,
    now: datetime | None = None,
    missing_file_grace_period_days: int | None = None,
    _result_factory: Callable[[], IngestResult] = IngestResult,
    _iter_photo_files: Callable[[Path], Iterable[Path]] | None = None,
    _generate_thumbnail: Callable[[Path], object] | None = None,
) -> IngestResult:
    source_root = Path(root).expanduser().resolve()
    result = _result_factory()
    at = now if now is not None else utc_now()
    grace_period_days = resolve_missing_file_grace_period_days(missing_file_grace_period_days)
    iter_photo_files_fn = _iter_photo_files or iter_photo_files
    generate_thumbnail_fn = _generate_thumbnail or generate_thumbnail

    engine = create_db_engine(database_url)
    with engine.begin() as connection:
        watched_folder_id = ensure_watched_folder_exists(
            connection,
            scan_path=source_root.as_posix(),
            now=at,
        )
        outcome = _reconcile_watched_folder_root(
            connection,
            watched_folder_id=watched_folder_id,
            source_root=source_root,
            canonical_path_for_relative_path=lambda relative_path: build_rooted_photo_path(
                source_root,
                relative_path,
            ),
            reuse_existing_photo_by_sha=False,
            now=at,
            missing_file_grace_period_days=grace_period_days,
            iter_photo_files_fn=iter_photo_files_fn,
            generate_thumbnail_fn=generate_thumbnail_fn,
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
    _result_factory: Callable[[], IngestResult] = IngestResult,
    _iter_photo_files: Callable[[Path], Iterable[Path]] | None = None,
    _generate_thumbnail: Callable[[Path], object] | None = None,
) -> IngestResult:
    result = _result_factory()
    at = now if now is not None else utc_now()
    grace_period_days = resolve_missing_file_grace_period_days(missing_file_grace_period_days)
    engine = create_db_engine(database_url)
    run_store = IngestRunStore(database_url)
    iter_photo_files_fn = _iter_photo_files or iter_photo_files
    generate_thumbnail_fn = _generate_thumbnail or generate_thumbnail

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
                    canonical_path_for_relative_path=_registered_source_path_builder(
                        storage_source_id=source_target.storage_source_id,
                        watched_folder_relative_path=target.relative_path,
                    ),
                    reuse_existing_photo_by_sha=True,
                    now=at,
                    missing_file_grace_period_days=grace_period_days,
                    iter_photo_files_fn=iter_photo_files_fn,
                    generate_thumbnail_fn=generate_thumbnail_fn,
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
    canonical_path_for_relative_path: Callable[[str], str],
    reuse_existing_photo_by_sha: bool,
    now: datetime,
    missing_file_grace_period_days: int,
    iter_photo_files_fn: Callable[[Path], Iterable[Path]],
    generate_thumbnail_fn: Callable[[Path], object],
) -> WatchedFolderPollOutcome:
    scanned = 0
    inserted = 0
    updated_count = 0
    error_messages: list[str] = []
    try:
        _validate_scan_root(source_root)
        scanned_paths = list(iter_photo_files_fn(source_root))
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
            canonical_path=canonical_path_for_relative_path(relative_path),
        )
        try:
            thumbnail = generate_thumbnail_fn(photo_path)
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
        if reuse_existing_photo_by_sha:
            created, photo_id = upsert_source_photo(connection, record)
        else:
            created = upsert_photo(connection, record)
            photo_id = record.photo_id
        if created:
            inserted += 1
        else:
            updated_count += 1
        touched_photo_ids.add(
            activate_observed_file(
                connection,
                watched_folder_id=watched_folder_id,
                photo_id=photo_id,
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


def _registered_source_path_builder(
    *,
    storage_source_id: str,
    watched_folder_relative_path: str | None,
) -> Callable[[str], str]:
    def build(relative_path: str) -> str:
        source_relative_parts = [
            part
            for part in (watched_folder_relative_path, relative_path)
            if part not in {None, ".", ""}
        ]
        source_relative_path = posixpath.normpath(posixpath.join(*source_relative_parts))
        return build_source_aware_photo_path(storage_source_id, source_relative_path)

    return build


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
