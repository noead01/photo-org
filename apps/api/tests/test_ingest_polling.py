from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select

from app.db.ingest_runs import IngestRunStore
from app.migrations import upgrade_database
from app.services.source_registration import MARKER_FILENAME, write_source_marker
from app.services.storage_sources import attach_storage_source_alias, create_storage_source
from app.services.watched_folders import create_watched_folder
from photoorg_db_schema import ingest_runs


def test_poll_registered_storage_sources_is_public_entrypoint():
    from app.processing.ingest_polling import poll_registered_storage_sources

    assert callable(poll_registered_storage_sources)


def test_load_registered_storage_source_targets_collects_enabled_watched_folders(tmp_path):
    from app.processing.ingest_polling import _load_registered_storage_source_targets

    database_url = f"sqlite:///{tmp_path / 'load-targets.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 23, 0, tzinfo=UTC)
    root = tmp_path / "source-root"
    watched = root / "imports"
    root.mkdir()
    watched.mkdir()

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
        created = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            watched_path=watched.as_posix(),
            display_name="Imports",
            now=now,
        )
        targets = _load_registered_storage_source_targets(connection)

    assert len(targets) == 1
    assert targets[0].storage_source_id == source["storage_source_id"]
    assert targets[0].alias_paths == (root.as_posix(),)
    assert targets[0].watched_folders[0].watched_folder_id == created["watched_folder_id"]
    assert targets[0].watched_folders[0].relative_path == "imports"


def test_validate_registered_source_target_prefers_valid_alias_root(tmp_path):
    from app.processing.ingest_polling import _validate_registered_source_target

    now = datetime(2026, 3, 28, 23, 15, tzinfo=UTC)
    root = tmp_path / "source-root"
    root.mkdir()
    missing_alias_root = tmp_path / "missing-root"

    database_url = f"sqlite:///{tmp_path / 'validate-target.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
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

    write_source_marker(root, storage_source_id=source["storage_source_id"])

    reason, detail, alias_root = _validate_registered_source_target(
        storage_source_id=source["storage_source_id"],
        alias_paths=(missing_alias_root.as_posix(), root.as_posix()),
    )

    assert reason is None
    assert detail is None
    assert alias_root == root.resolve()


def test_registered_source_path_builder_joins_relative_paths(tmp_path):
    from app.processing.ingest_polling import _registered_source_path_builder

    builder = _registered_source_path_builder(
        storage_source_id="source-1",
        watched_folder_relative_path="imports",
    )

    assert builder("family-events/../birthday-park/birthday_park_001.jpg") == (
        "/storage-sources/source-1/imports/birthday-park/birthday_park_001.jpg"
    )


def test_record_ingest_run_finalizes_run_with_error_summary(tmp_path):
    from app.processing.ingest_polling import _record_ingest_run

    database_url = f"sqlite:///{tmp_path / 'record-run.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    run_store = IngestRunStore(database_url)
    now = datetime(2026, 3, 29, 0, 0, tzinfo=UTC)

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
            alias_path=(tmp_path / "source-root").as_posix(),
            now=now,
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=(tmp_path / "source-root").as_posix(),
            watched_path=(tmp_path / "source-root").as_posix(),
            display_name="Source Root",
            now=now,
        )
        _record_ingest_run(
            run_store,
            connection=connection,
            watched_folder_id=watched_folder["watched_folder_id"],
            status="failed",
            files_seen=3,
            files_created=1,
            files_updated=2,
            error_messages=("first problem", "second problem"),
        )
        run_row = connection.execute(select(ingest_runs)).mappings().one()

    assert run_row["watched_folder_id"] == watched_folder["watched_folder_id"]
    assert run_row["status"] == "failed"
    assert run_row["files_seen"] == 3
    assert run_row["files_created"] == 1
    assert run_row["files_updated"] == 2
    assert run_row["error_count"] == 2
    assert run_row["error_summary"] == "first problem"
