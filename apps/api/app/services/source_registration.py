from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.services.path_normalization import PathNormalizationError, normalize_operator_path
from app.storage import create_db_engine
from app.services.storage_sources import (
    StorageSourceConflictError,
    attach_storage_source_alias,
    create_storage_source,
    get_storage_source_by_marker_id,
)


MARKER_FILENAME = ".photo-org-source.json"
MARKER_VERSION = 1


class SourceRegistrationError(RuntimeError):
    pass


def register_storage_source(
    *,
    database_url: str | Path | None,
    root_path: str | Path,
    alias_path: str | Path | None = None,
    display_name: str | None = None,
) -> dict[str, object]:
    root = Path(root_path).expanduser().resolve()
    if not root.exists():
        raise SourceRegistrationError(f"storage source root does not exist: {root}")
    if not root.is_dir():
        raise SourceRegistrationError(f"storage source root is not a directory: {root}")

    try:
        alias = (
            normalize_operator_path(str(alias_path))
            if alias_path is not None
            else normalize_operator_path(root.as_posix())
        )
    except PathNormalizationError as exc:
        raise SourceRegistrationError(str(exc)) from exc
    now = datetime.now(tz=UTC)
    engine = create_db_engine(database_url)
    marker = read_source_marker(root)

    try:
        with engine.begin() as connection:
            if marker is None:
                source = create_storage_source(
                    connection,
                    display_name=display_name or root.name,
                    marker_filename=MARKER_FILENAME,
                    marker_version=MARKER_VERSION,
                    now=now,
                )
                write_source_marker(root, storage_source_id=str(source["storage_source_id"]))
            else:
                if marker.get("marker_version") != MARKER_VERSION:
                    raise SourceRegistrationError(
                        f"unsupported marker version: {marker.get('marker_version')}"
                    )
                source = get_storage_source_by_marker_id(
                    connection,
                    str(marker["storage_source_id"]),
                )
                if source is None:
                    raise SourceRegistrationError(
                        f"marker file references unknown storage source: {marker['storage_source_id']}"
                    )

            attach_storage_source_alias(
                connection,
                storage_source_id=str(source["storage_source_id"]),
                alias_path=alias,
                now=now,
            )
            return source
    except StorageSourceConflictError as exc:
        raise SourceRegistrationError(str(exc)) from exc
    finally:
        engine.dispose()


def read_source_marker(root: Path) -> dict[str, object] | None:
    marker_path = root / MARKER_FILENAME
    if not marker_path.is_file():
        return None
    try:
        marker = json.loads(marker_path.read_text())
    except json.JSONDecodeError as exc:
        raise SourceRegistrationError(f"malformed storage source marker file: {marker_path}") from exc
    if not isinstance(marker, dict):
        raise SourceRegistrationError(f"malformed storage source marker file: {marker_path}")
    if "storage_source_id" not in marker:
        raise SourceRegistrationError(
            f"malformed storage source marker file missing storage_source_id: {marker_path}"
        )
    return marker


def write_source_marker(root: Path, *, storage_source_id: str) -> None:
    marker_path = root / MARKER_FILENAME
    payload = {
        "storage_source_id": storage_source_id,
        "marker_version": MARKER_VERSION,
    }
    marker_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
