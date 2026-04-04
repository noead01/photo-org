from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

from app.migrations import upgrade_database
from app.services.source_registration import MARKER_FILENAME, write_source_marker
from app.services.storage_sources import attach_storage_source_alias, create_storage_source
from app.services.watched_folders import create_watched_folder
from app.storage import photos, storage_sources, watched_folders
from photoorg_db_schema import ingest_runs

pytest.importorskip("PIL")
from PIL import Image


def _write_test_image(path: Path) -> None:
    image = Image.new("RGB", (2, 2), color=(255, 0, 0))
    image.save(path, format="JPEG")


def test_poll_registered_storage_sources_processes_a_registered_source_end_to_end(tmp_path):
    from app.processing.ingest_polling import poll_registered_storage_sources

    database_url = f"sqlite:///{tmp_path / 'poll-happy-path.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 29, 0, 0, tzinfo=UTC)

    root = tmp_path / "source-root"
    watched = root / "imports"
    watched.mkdir(parents=True)
    _write_test_image(watched / "birthday_park_001.jpg")

    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Source",
            marker_filename=MARKER_FILENAME,
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            now=now,
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            watched_path=watched.as_posix(),
            display_name="Imports",
            now=now,
        )
        write_source_marker(root, storage_source_id=source["storage_source_id"])

    result = poll_registered_storage_sources(database_url=database_url, now=now)

    assert result.scanned == 1
    assert result.inserted == 1
    assert result.updated == 0
    assert result.errors == []
    expected_now = now.replace(tzinfo=None)

    with engine.connect() as connection:
        source_row = connection.execute(
            select(
                storage_sources.c.availability_state,
                storage_sources.c.last_failure_reason,
                storage_sources.c.last_validated_ts,
            ).where(storage_sources.c.storage_source_id == source["storage_source_id"])
        ).mappings().one()
        watched_folder_row = connection.execute(
            select(
                watched_folders.c.availability_state,
                watched_folders.c.last_failure_reason,
                watched_folders.c.last_successful_scan_ts,
            ).where(watched_folders.c.watched_folder_id == watched_folder["watched_folder_id"])
        ).mappings().one()
        run_row = connection.execute(select(ingest_runs)).mappings().one()
        photo_count = connection.execute(select(func.count()).select_from(photos)).scalar_one()

    assert source_row["availability_state"] == "active"
    assert source_row["last_failure_reason"] is None
    assert source_row["last_validated_ts"] == expected_now
    assert watched_folder_row["availability_state"] == "active"
    assert watched_folder_row["last_failure_reason"] is None
    assert watched_folder_row["last_successful_scan_ts"] == expected_now
    assert run_row["watched_folder_id"] == watched_folder["watched_folder_id"]
    assert run_row["status"] == "completed"
    assert run_row["files_seen"] == 1
    assert run_row["files_created"] == 1
    assert run_row["files_updated"] == 0
    assert run_row["error_count"] == 0
    assert photo_count == 1


def test_poll_registered_storage_sources_records_one_completed_run_per_chunk(tmp_path):
    from app.processing.ingest_polling import poll_registered_storage_sources

    database_url = f"sqlite:///{tmp_path / 'poll-chunked-runs.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 4, 4, 12, 0, tzinfo=UTC)

    root = tmp_path / "source-root"
    watched = root / "imports"
    watched.mkdir(parents=True)
    for index in range(5):
        _write_test_image(watched / f"photo_{index:03d}.jpg")

    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Source",
            marker_filename=MARKER_FILENAME,
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            now=now,
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            watched_path=watched.as_posix(),
            display_name="Imports",
            now=now,
        )
        write_source_marker(root, storage_source_id=source["storage_source_id"])

    result = poll_registered_storage_sources(
        database_url=database_url,
        now=now,
        poll_chunk_size=2,
    )

    assert result.scanned == 5
    with engine.connect() as connection:
        run_rows = list(
            connection.execute(
                select(ingest_runs)
                .where(ingest_runs.c.watched_folder_id == watched_folder["watched_folder_id"])
                .order_by(ingest_runs.c.started_ts, ingest_runs.c.ingest_run_id)
            ).mappings()
        )

    assert [(row["status"], row["files_seen"]) for row in run_rows] == [
        ("completed", 2),
        ("completed", 2),
        ("completed", 1),
    ]


def test_reconcile_directory_processes_a_watched_folder_end_to_end(tmp_path):
    from app.processing.ingest_polling import reconcile_directory

    database_url = f"sqlite:///{tmp_path / 'reconcile-happy-path.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 29, 0, 15, tzinfo=UTC)

    root = tmp_path / "watched-folder"
    root.mkdir(parents=True)
    _write_test_image(root / "birthday_park_001.jpg")

    result = reconcile_directory(root, database_url=database_url, now=now)

    assert result.scanned == 1
    assert result.inserted == 1
    assert result.updated == 0
    assert result.errors == []
    expected_now = now.replace(tzinfo=None)

    with engine.connect() as connection:
        watched_folder_row = connection.execute(
            select(
                watched_folders.c.availability_state,
                watched_folders.c.last_failure_reason,
                watched_folders.c.last_successful_scan_ts,
            ).where(watched_folders.c.scan_path == root.as_posix())
        ).mappings().one()
        photo_count = connection.execute(select(func.count()).select_from(photos)).scalar_one()

    assert watched_folder_row["availability_state"] == "active"
    assert watched_folder_row["last_failure_reason"] is None
    assert watched_folder_row["last_successful_scan_ts"] == expected_now
    assert photo_count == 1


def test_ingest_polling_reconcile_directory_does_not_depend_on_ingest_facade(tmp_path, monkeypatch):
    import importlib.util
    import sys
    import types

    import app.processing
    import app.processing.ingest_polling as ingest_polling_module

    database_url = f"sqlite:///{tmp_path / 'reconcile-no-facade-dependency.db'}"
    upgrade_database(database_url)

    root = tmp_path / "isolated-watched-folder"
    root.mkdir(parents=True)
    _write_test_image(root / "birthday_park_001.jpg")

    fake_ingest_module = types.ModuleType("app.processing.ingest")
    monkeypatch.setattr(app.processing, "ingest", fake_ingest_module, raising=False)
    monkeypatch.setitem(sys.modules, "app.processing.ingest", fake_ingest_module)

    spec = importlib.util.spec_from_file_location(
        "isolated_ingest_polling",
        Path(ingest_polling_module.__file__),
    )
    assert spec is not None and spec.loader is not None
    isolated_ingest_polling = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, isolated_ingest_polling)
    spec.loader.exec_module(isolated_ingest_polling)

    result = isolated_ingest_polling.reconcile_directory(root, database_url=database_url)

    assert result.scanned == 1
    assert result.inserted == 1
    assert result.updated == 0
    assert result.errors == []
