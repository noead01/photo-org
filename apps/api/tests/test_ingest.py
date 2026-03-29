from datetime import UTC, datetime, timedelta
import posixpath
import shutil
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy import create_engine, event, func, insert, select, update

from app.db.queue import IngestQueueStore
from app.migrations import upgrade_database
from app.processing import ingest as ingest_module
from app.processing.ingest import (
    ingest_directory,
    poll_registered_storage_sources,
    reconcile_directory,
)
from app.services.file_reconciliation import (
    activate_observed_file,
    reconcile_watched_folder,
    refresh_photo_deleted_timestamps,
)
from app.services.source_registration import MARKER_FILENAME
from app.services.storage_sources import attach_storage_source_alias, create_storage_source
from app.services.watched_folders import create_watched_folder
from app.storage import faces, photo_files, photos, storage_sources, watched_folders
from photoorg_db_schema import ingest_runs


def _resolve_seed_corpus_dir(start: Path | None = None) -> Path:
    test_file = (start or Path(__file__)).resolve()
    for parent in [test_file.parent, *test_file.parents]:
        candidate = parent / "seed-corpus"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not locate seed-corpus from test_ingest.py")


SEED_CORPUS_DIR = _resolve_seed_corpus_dir()
SEED_CORPUS_SUBSET_PATHS = (
    "seed-corpus/family-events/birthday-park/birthday_park_001.jpg",
    "seed-corpus/family-events/birthday-park/birthday_park_002.jpeg",
    "seed-corpus/family-events/birthday-park/birthday_park_003.heic",
    "seed-corpus/family-events/birthday-park/birthday_park_004.png",
    "seed-corpus/family-events/birthday-park/birthday_park_005.jpg",
    "seed-corpus/family-events/birthday-park/birthday_park_006.jpg",
)
SEED_CORPUS_RELATIVE_SUBSET_PATHS = tuple(
    asset_path.removeprefix("seed-corpus/") for asset_path in SEED_CORPUS_SUBSET_PATHS
)


PIL = pytest.importorskip("PIL")
pytest.importorskip("pillow_heif")


def test_resolve_seed_corpus_dir_finds_a_worktree_layout(tmp_path):
    repo_root = tmp_path / "repo"
    seed_corpus_dir = repo_root / "seed-corpus"
    seed_corpus_dir.mkdir(parents=True)

    worktree_test_file = repo_root / ".worktrees" / "issue-18-compose-dev-stack" / "apps" / "api" / "tests" / "test_ingest.py"
    worktree_test_file.parent.mkdir(parents=True)
    worktree_test_file.write_text("")

    assert _resolve_seed_corpus_dir(worktree_test_file) == seed_corpus_dir


def _stage_seed_corpus_subset(destination_root: Path) -> Path:
    staged_root = destination_root / "seed-corpus"
    for asset_path in SEED_CORPUS_SUBSET_PATHS:
        relative_path = asset_path.removeprefix("seed-corpus/")
        source = SEED_CORPUS_DIR / relative_path
        target = staged_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return staged_root


def test_ingest_directory_loads_sample_photos_into_queue(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'photoorg.db'}"
    upgrade_database(db_url)

    result = ingest_directory(
        staged_corpus_dir,
        database_url=db_url,
    )

    assert result.scanned == 6
    assert result.enqueued == 6
    assert result.inserted == 0
    assert result.updated == 0
    assert result.errors == []

    rows = load_pending_queue_rows(db_url)

    assert len(rows) == 6
    assert all(row.payload_type == "photo_metadata" for row in rows)
    assert all(row.payload_json["path"].startswith(f"{staged_corpus_dir.as_posix()}/") for row in rows)
    assert {row.payload_json["ext"] for row in rows} == {"jpg", "jpeg", "png", "heic"}
    assert all(row.payload_json["filesize"] > 0 for row in rows)
    assert all(len(row.payload_json["sha256"]) == 64 for row in rows)
    assert all(row.payload_json["faces_count"] == 0 for row in rows)
    sample = next(row for row in rows if row.payload_json["path"].endswith("birthday_park_005.jpg"))
    assert sample.payload_json["shot_ts"] == "2022-06-14T15:28:00+00:00"
    assert sample.payload_json["shot_ts_source"] == "exif:DateTime"
    assert sample.payload_json["camera_make"] == "Apple"
    assert sample.payload_json["camera_model"] == "iPhone 12 mini"
    assert sample.payload_json["gps_latitude"] is None
    assert sample.payload_json["gps_longitude"] is None
    assert load_photo_count(db_url) == 0


def test_ingest_directory_enqueues_records_without_writing_photos_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'queue-ingest.db'}"
    upgrade_database(db_url)

    result = ingest_directory(
        staged_corpus_dir,
        database_url=db_url,
    )

    assert result.scanned == 6
    assert result.enqueued == 6
    assert load_photo_count(db_url) == 0
    assert load_pending_queue_count(db_url) == 6


def test_ingest_directory_is_idempotent_for_existing_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'photoorg.db'}"
    upgrade_database(db_url)

    first_run = ingest_directory(
        staged_corpus_dir,
        database_url=db_url,
    )
    second_run = ingest_directory(
        staged_corpus_dir,
        database_url=db_url,
    )

    assert first_run.enqueued == 6
    assert second_run.enqueued == 6
    assert second_run.inserted == 0
    assert second_run.updated == 0
    assert second_run.errors == []
    assert load_photo_count(db_url) == 0
    assert load_pending_queue_count(db_url) == 6


def test_ingest_directory_keeps_domain_tables_unwritten_when_detector_is_enabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'faces.db'}"
    upgrade_database(db_url)

    result = ingest_directory(
        staged_corpus_dir,
        database_url=db_url,
        face_detector=UnusedFaceDetector(),
    )

    assert result.errors == []
    assert result.enqueued == 6
    assert load_photo_count(db_url) == 0
    assert load_face_count(db_url) == 0
    assert load_pending_queue_count(db_url) == 6


def test_ingest_directory_keeps_queue_only_behavior(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'chunk-threshold.db'}"
    upgrade_database(db_url)

    result = ingest_directory(
        staged_corpus_dir,
        database_url=db_url,
    )

    assert result.errors == []
    assert result.scanned == 6
    assert result.enqueued == 6
    assert load_pending_queue_count(db_url) == 6
    assert load_photo_count(db_url) == 0


def test_upgrade_database_creates_search_tables(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'schema.db'}"
    upgrade_database(db_url)
    engine = create_engine(db_url, future=True)

    with engine.connect() as connection:
        tables = set(connection.dialect.get_table_names(connection))

    assert {"photos", "faces", "photo_tags", "people", "face_labels"} <= tables


def test_reconcile_directory_marks_absent_files_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-missing.db'}"
    upgrade_database(db_url)

    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
    )

    missing_path = staged_corpus_dir / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    missing_path.unlink()

    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
    )

    row = load_photo_file_row(db_url, "family-events/birthday-park/birthday_park_006.jpg")
    assert row["lifecycle_state"] == "missing"
    assert row["missing_ts"] is not None
    assert row["deleted_ts"] is None

    watched_folder = load_watched_folder_row(db_url, staged_corpus_dir.as_posix())
    assert watched_folder["availability_state"] == "active"
    assert watched_folder["last_failure_reason"] is None
    assert watched_folder["last_successful_scan_ts"] is not None


def test_reconcile_directory_deletes_missing_file_after_grace_period(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-grace.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 24, tzinfo=UTC)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=now,
    )

    missing_path = staged_corpus_dir / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    missing_path.unlink()

    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=now,
    )
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=now + timedelta(days=1, seconds=1),
    )

    row = load_photo_file_row(
        db_url,
        "family-events/birthday-park/birthday_park_006.jpg",
    )
    assert row["lifecycle_state"] == "deleted"
    assert row["missing_ts"] == now
    assert row["deleted_ts"] == now + timedelta(days=1, seconds=1)

    watched_folder = load_watched_folder_row(db_url, staged_corpus_dir.as_posix())
    assert watched_folder["availability_state"] == "active"
    assert watched_folder["last_failure_reason"] is None
    assert watched_folder["last_successful_scan_ts"] == now + timedelta(days=1, seconds=1)


def test_reconcile_directory_with_zero_day_grace_immediately_deletes_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-zero-grace.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 24, tzinfo=UTC)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=now,
        missing_file_grace_period_days=0,
    )

    missing_path = staged_corpus_dir / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    missing_path.unlink()

    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=now,
        missing_file_grace_period_days=0,
    )

    row = load_photo_file_row(
        db_url,
        "family-events/birthday-park/birthday_park_006.jpg",
    )
    assert row["lifecycle_state"] == "deleted"
    assert row["missing_ts"] == now
    assert row["deleted_ts"] == now

    watched_folder = load_watched_folder_row(db_url, staged_corpus_dir.as_posix())
    assert watched_folder["availability_state"] == "active"
    assert watched_folder["last_failure_reason"] is None
    assert watched_folder["last_successful_scan_ts"] == now


def test_reconcile_directory_marks_watched_folder_unreachable_when_root_scan_fails(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-unreachable.db'}"
    upgrade_database(db_url)

    healthy_now = datetime(2026, 3, 24, tzinfo=UTC)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=healthy_now,
    )

    watched_folder = load_watched_folder_row(db_url, staged_corpus_dir.as_posix())
    assert watched_folder["availability_state"] == "active"
    assert watched_folder["last_failure_reason"] is None
    assert watched_folder["last_successful_scan_ts"] == healthy_now

    monkeypatch.setattr("app.processing.ingest.iter_photo_files", _fail_root_scan)

    failure_now = healthy_now + timedelta(minutes=1)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=failure_now,
    )

    row = load_watched_folder_row(db_url, staged_corpus_dir.as_posix())
    assert row["availability_state"] == "unreachable"
    assert row["last_successful_scan_ts"] == healthy_now


def test_reconcile_directory_preserves_last_successful_scan_ts_when_root_scan_fails(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-preserve-successful-scan-ts.db'}"
    upgrade_database(db_url)

    healthy_now = datetime(2026, 3, 24, tzinfo=UTC)
    failure_now = healthy_now + timedelta(minutes=1)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=healthy_now,
    )

    monkeypatch.setattr("app.processing.ingest.iter_photo_files", _fail_root_scan)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=failure_now,
    )

    row = load_watched_folder_row(db_url, staged_corpus_dir.as_posix())
    assert row["availability_state"] == "unreachable"
    assert row["last_failure_reason"] == "permission_denied"
    assert row["last_successful_scan_ts"] == healthy_now


@pytest.mark.parametrize(("root_kind",), [("missing",), ("file",)])
def test_reconcile_directory_marks_missing_or_non_directory_root_unreachable(
    tmp_path, monkeypatch, root_kind
):
    monkeypatch.chdir(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-folder-unmounted.db'}"
    upgrade_database(db_url)

    if root_kind == "missing":
        root = tmp_path / "missing-root"
    else:
        root = _create_non_directory_root(tmp_path)

    reconcile_directory(root, database_url=db_url, now=datetime(2026, 3, 24, tzinfo=UTC))

    row = load_watched_folder_row(db_url, root.resolve().as_posix())
    assert row["availability_state"] == "unreachable"
    assert row["last_failure_reason"] == "folder_unmounted"
    assert row["last_successful_scan_ts"] is None


def test_reconcile_directory_does_not_advance_file_lifecycle_when_root_scan_fails(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-root-failure.db'}"
    upgrade_database(db_url)

    healthy_now = datetime(2026, 3, 24, tzinfo=UTC)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=healthy_now,
    )

    before = load_photo_file_row(
        db_url,
        "family-events/birthday-park/birthday_park_006.jpg",
    )

    monkeypatch.setattr("app.processing.ingest.iter_photo_files", _fail_root_scan)

    failure_now = healthy_now + timedelta(minutes=1)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=failure_now,
    )

    after = load_photo_file_row(
        db_url,
        "family-events/birthday-park/birthday_park_006.jpg",
    )
    assert after["lifecycle_state"] == before["lifecycle_state"]
    assert after["missing_ts"] == before["missing_ts"]
    assert after["deleted_ts"] == before["deleted_ts"]


def test_reconcile_directory_preserves_parent_photo_deleted_timestamp_when_root_scan_fails(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-root-failure-parent-photo.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 24, tzinfo=UTC)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=now,
    )

    missing_path = staged_corpus_dir / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    missing_path.unlink()

    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=now,
    )
    deleted_now = now + timedelta(days=1, seconds=1)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=deleted_now,
    )

    deleted_row = load_photo_file_row(
        db_url,
        "family-events/birthday-park/birthday_park_006.jpg",
    )
    deleted_before = load_photo_deleted_ts(
        db_url,
        deleted_row["photo_id"],
    )
    assert deleted_before == deleted_now

    monkeypatch.setattr("app.processing.ingest.iter_photo_files", _fail_root_scan)

    failure_now = deleted_now + timedelta(minutes=1)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=failure_now,
    )

    deleted_after = load_photo_deleted_ts(
        db_url,
        deleted_row["photo_id"],
    )
    assert deleted_after == deleted_before


def test_reconcile_directory_clears_unreachable_state_after_later_healthy_scan(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-recovery.db'}"
    upgrade_database(db_url)

    healthy_now = datetime(2026, 3, 24, tzinfo=UTC)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=healthy_now,
    )

    original_iter_photo_files = ingest_module.iter_photo_files
    monkeypatch.setattr("app.processing.ingest.iter_photo_files", _fail_root_scan)

    failure_now = healthy_now + timedelta(minutes=1)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=failure_now,
    )

    monkeypatch.setattr(
        "app.processing.ingest.iter_photo_files",
        original_iter_photo_files,
    )

    recovered_now = healthy_now + timedelta(minutes=2)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=recovered_now,
    )

    row = load_watched_folder_row(db_url, staged_corpus_dir.as_posix())
    assert row["availability_state"] == "active"
    assert row["last_failure_reason"] is None
    assert row["last_successful_scan_ts"] == recovered_now


def test_reconcile_directory_persists_thumbnail_and_keeps_it_when_source_goes_offline(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-thumbnails.db'}"
    upgrade_database(db_url)

    healthy_now = datetime(2026, 3, 28, 19, 0, tzinfo=UTC)
    source_id = seed_linked_storage_source(
        db_url,
        scan_root=staged_corpus_dir,
        now=healthy_now,
    )

    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=healthy_now,
    )

    photo = load_photo_row(
        db_url,
        f"{staged_corpus_dir.as_posix()}/family-events/birthday-park/birthday_park_001.jpg",
    )
    assert photo["thumbnail_mime_type"] == "image/jpeg"
    assert photo["thumbnail_width"] > 0
    assert photo["thumbnail_height"] > 0
    assert isinstance(photo["thumbnail_jpeg"], bytes)
    assert len(photo["thumbnail_jpeg"]) > 0

    monkeypatch.setattr("app.processing.ingest.iter_photo_files", _fail_root_scan)

    offline_now = healthy_now + timedelta(minutes=1)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=offline_now,
    )

    source = load_storage_source_row(db_url, source_id)
    assert source["availability_state"] == "unreachable"
    assert source["last_failure_reason"] == "permission_denied"

    preserved = load_photo_row(
        db_url,
        f"{staged_corpus_dir.as_posix()}/family-events/birthday-park/birthday_park_001.jpg",
    )
    assert preserved["thumbnail_jpeg"] == photo["thumbnail_jpeg"]
    assert preserved["thumbnail_width"] == photo["thumbnail_width"]
    assert preserved["thumbnail_height"] == photo["thumbnail_height"]


def test_reconcile_directory_reports_thumbnail_failures_without_marking_source_unreachable(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'reconcile-thumbnail-errors.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 28, 19, 30, tzinfo=UTC)
    source_id = seed_linked_storage_source(
        db_url,
        scan_root=staged_corpus_dir,
        now=now,
    )

    monkeypatch.setattr(
        "app.processing.ingest.generate_thumbnail",
        lambda _: (_ for _ in ()).throw(RuntimeError("thumbnail exploded")),
    )

    result = reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        now=now,
    )

    assert result.scanned == 6
    assert result.inserted == 6
    assert result.updated == 0
    assert len(result.errors) == 6
    assert all("thumbnail exploded" in error for error in result.errors)

    source = load_storage_source_row(db_url, source_id)
    assert source["availability_state"] == "active"
    assert source["last_failure_reason"] is None

    photo = load_photo_row(
        db_url,
        f"{staged_corpus_dir.as_posix()}/family-events/birthday-park/birthday_park_001.jpg",
    )
    assert photo["thumbnail_jpeg"] is None


def test_poll_registered_storage_sources_scans_enabled_registered_watched_folders(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'poll-storage-sources.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 28, 21, 0, tzinfo=UTC)
    source_id, watched_folder_id = seed_registered_storage_source_with_watched_folder(
        db_url,
        root_path=staged_corpus_dir,
        watched_path=staged_corpus_dir,
        display_name="Seed Corpus",
        now=now,
    )

    result = poll_registered_storage_sources(database_url=db_url, now=now)

    assert result.scanned == 6
    assert result.inserted == 6
    assert result.updated == 0
    assert result.errors == []

    watched_folder = load_watched_folder_by_id(db_url, watched_folder_id)
    assert watched_folder["availability_state"] == "active"
    assert watched_folder["last_failure_reason"] is None
    assert watched_folder["last_successful_scan_ts"] == now

    source = load_storage_source_row(db_url, source_id)
    assert source["availability_state"] == "active"
    assert source["last_failure_reason"] is None
    assert source["last_validated_ts"] == now

    photo = load_photo_row(
        db_url,
        _source_aware_photo_path(
            source_id,
            "family-events/birthday-park/birthday_park_001.jpg",
        ),
    )
    assert photo["thumbnail_mime_type"] == "image/jpeg"


def test_poll_registered_storage_sources_ignores_legacy_scan_path_for_identity(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'poll-storage-sources-source-aware-paths.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 28, 21, 15, tzinfo=UTC)
    source_id, watched_folder_id = seed_registered_storage_source_with_watched_folder(
        db_url,
        root_path=staged_corpus_dir,
        watched_path=staged_corpus_dir,
        display_name="Seed Corpus",
        now=now,
    )
    engine = create_engine(db_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            update(watched_folders)
            .where(watched_folders.c.watched_folder_id == watched_folder_id)
            .values(scan_path="/legacy/photos/seed-corpus")
        )

    result = poll_registered_storage_sources(database_url=db_url, now=now)

    assert result.errors == []
    photo = load_photo_row(
        db_url,
        _source_aware_photo_path(
            source_id,
            "family-events/birthday-park/birthday_park_001.jpg",
        ),
    )
    assert photo["path"] == _source_aware_photo_path(
        source_id,
        "family-events/birthday-park/birthday_park_001.jpg",
    )
    assert not photo["path"].startswith("/legacy/photos/")


def test_poll_registered_storage_sources_aborts_reconciliation_on_marker_mismatch(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'poll-storage-sources-marker-mismatch.db'}"
    upgrade_database(db_url)

    healthy_now = datetime(2026, 3, 28, 21, 30, tzinfo=UTC)
    source_id, watched_folder_id = seed_registered_storage_source_with_watched_folder(
        db_url,
        root_path=staged_corpus_dir,
        watched_path=staged_corpus_dir,
        display_name="Seed Corpus",
        now=healthy_now,
    )

    first_result = poll_registered_storage_sources(database_url=db_url, now=healthy_now)
    assert first_result.errors == []

    missing_path = staged_corpus_dir / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    missing_path.unlink()
    (staged_corpus_dir / MARKER_FILENAME).write_text(
        '{"storage_source_id":"unexpected-source","marker_version":1}'
    )

    failed_now = healthy_now + timedelta(minutes=5)
    failed_result = poll_registered_storage_sources(database_url=db_url, now=failed_now)

    assert failed_result.scanned == 0
    assert failed_result.inserted == 0
    assert failed_result.updated == 0
    assert failed_result.errors == [
        f"storage_source:{source_id}: marker file does not match expected storage source"
    ]

    source = load_storage_source_row(db_url, source_id)
    assert source["availability_state"] == "unreachable"
    assert source["last_failure_reason"] == "marker_mismatch"
    assert source["last_validated_ts"] == failed_now

    watched_folder = load_watched_folder_by_id(db_url, watched_folder_id)
    assert watched_folder["availability_state"] == "unreachable"
    assert watched_folder["last_failure_reason"] == "marker_mismatch"
    assert watched_folder["last_successful_scan_ts"] == healthy_now

    photo_file = load_photo_file_row(
        db_url,
        "family-events/birthday-park/birthday_park_006.jpg",
    )
    assert photo_file["lifecycle_state"] == "active"
    assert photo_file["missing_ts"] is None
    assert photo_file["deleted_ts"] is None


def test_poll_registered_storage_sources_reports_missing_marker_file(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'poll-storage-sources-marker-missing.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 28, 21, 45, tzinfo=UTC)
    source_id, watched_folder_id = seed_registered_storage_source_with_watched_folder(
        db_url,
        root_path=staged_corpus_dir,
        watched_path=staged_corpus_dir,
        display_name="Seed Corpus",
        now=now,
    )
    (staged_corpus_dir / MARKER_FILENAME).unlink()

    result = poll_registered_storage_sources(database_url=db_url, now=now)

    assert result.scanned == 0
    assert result.errors == [f"storage_source:{source_id}: storage source marker file is missing"]

    source = load_storage_source_row(db_url, source_id)
    assert source["availability_state"] == "unreachable"
    assert source["last_failure_reason"] == "marker_missing"
    assert source["last_validated_ts"] == now

    watched_folder = load_watched_folder_by_id(db_url, watched_folder_id)
    assert watched_folder["availability_state"] == "unreachable"
    assert watched_folder["last_failure_reason"] == "marker_missing"


def test_poll_registered_storage_sources_reports_unreachable_source_root(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'poll-storage-sources-root-unreachable.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 28, 22, 0, tzinfo=UTC)
    source_id, watched_folder_id = seed_registered_storage_source_with_watched_folder(
        db_url,
        root_path=staged_corpus_dir,
        watched_path=staged_corpus_dir,
        display_name="Seed Corpus",
        now=now,
    )
    shutil.rmtree(staged_corpus_dir)

    result = poll_registered_storage_sources(database_url=db_url, now=now)

    assert result.scanned == 0
    assert result.errors == [f"storage_source:{source_id}: storage source root is unavailable"]

    source = load_storage_source_row(db_url, source_id)
    assert source["availability_state"] == "unreachable"
    assert source["last_failure_reason"] == "source_unreachable"
    assert source["last_validated_ts"] == now

    watched_folder = load_watched_folder_by_id(db_url, watched_folder_id)
    assert watched_folder["availability_state"] == "unreachable"
    assert watched_folder["last_failure_reason"] == "source_unreachable"


def test_poll_registered_storage_sources_falls_back_to_later_alias_when_first_is_unreachable(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    missing_alias_root = tmp_path / "missing-alias-root"
    db_url = f"sqlite:///{tmp_path / 'poll-storage-sources-alias-fallback.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 28, 22, 30, tzinfo=UTC)
    source_id, watched_folder_id = seed_registered_storage_source_with_watched_folder(
        db_url,
        root_path=staged_corpus_dir,
        watched_path=staged_corpus_dir,
        display_name="Seed Corpus",
        now=now,
        alias_paths=(missing_alias_root.as_posix(), staged_corpus_dir.as_posix()),
    )

    result = poll_registered_storage_sources(database_url=db_url, now=now)

    assert result.scanned == 6
    assert result.errors == []

    source = load_storage_source_row(db_url, source_id)
    assert source["availability_state"] == "active"
    assert source["last_failure_reason"] is None

    watched_folder = load_watched_folder_by_id(db_url, watched_folder_id)
    assert watched_folder["availability_state"] == "active"
    assert watched_folder["last_successful_scan_ts"] == now


def test_poll_registered_storage_sources_records_ingest_run_for_successful_scan(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'poll-storage-sources-ingest-run-success.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 28, 22, 45, tzinfo=UTC)
    _, watched_folder_id = seed_registered_storage_source_with_watched_folder(
        db_url,
        root_path=staged_corpus_dir,
        watched_path=staged_corpus_dir,
        display_name="Seed Corpus",
        now=now,
    )

    result = poll_registered_storage_sources(database_url=db_url, now=now)

    assert result.scanned == 6

    run_rows = load_ingest_runs(database_url=db_url)
    assert len(run_rows) == 1
    assert run_rows[0]["watched_folder_id"] == watched_folder_id
    assert run_rows[0]["status"] == "completed"
    assert run_rows[0]["files_seen"] == 6
    assert run_rows[0]["files_created"] == 6
    assert run_rows[0]["files_updated"] == 0
    assert run_rows[0]["error_count"] == 0
    assert run_rows[0]["error_summary"] is None


def test_poll_registered_storage_sources_records_ingest_run_for_source_validation_failure(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'poll-storage-sources-ingest-run-failure.db'}"
    upgrade_database(db_url)

    now = datetime(2026, 3, 28, 23, 0, tzinfo=UTC)
    source_id, watched_folder_id = seed_registered_storage_source_with_watched_folder(
        db_url,
        root_path=staged_corpus_dir,
        watched_path=staged_corpus_dir,
        display_name="Seed Corpus",
        now=now,
    )
    (staged_corpus_dir / MARKER_FILENAME).unlink()

    result = poll_registered_storage_sources(database_url=db_url, now=now)

    assert result.errors == [f"storage_source:{source_id}: storage source marker file is missing"]

    run_rows = load_ingest_runs(database_url=db_url)
    assert len(run_rows) == 1
    assert run_rows[0]["watched_folder_id"] == watched_folder_id
    assert run_rows[0]["status"] == "failed"
    assert run_rows[0]["files_seen"] == 0
    assert run_rows[0]["files_created"] == 0
    assert run_rows[0]["files_updated"] == 0
    assert run_rows[0]["error_count"] == 1
    assert run_rows[0]["error_summary"] == "storage source marker file is missing"


def test_upsert_photo_skips_thumbnail_lookup_when_record_has_fresh_thumbnail(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'upsert-photo-thumbnail-fast-path.db'}"
    upgrade_database(database_url)
    now = datetime(2026, 3, 28, 20, 0, tzinfo=UTC)
    path = "/test-root/family-events/birthday-park/birthday_park_001.jpg"

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                path=path,
                sha256="a" * 64,
                phash=None,
                filesize=100,
                ext="jpg",
                created_ts=now,
                modified_ts=now,
                shot_ts=None,
                shot_ts_source=None,
                camera_make=None,
                camera_model=None,
                software=None,
                orientation=None,
                gps_latitude=None,
                gps_longitude=None,
                gps_altitude=None,
                thumbnail_jpeg=b"old-thumbnail",
                thumbnail_mime_type="image/jpeg",
                thumbnail_width=64,
                thumbnail_height=48,
                updated_ts=now,
                faces_count=0,
                faces_detected_ts=None,
            )
        )

    statements: list[str] = []

    @event.listens_for(engine, "before_execute")
    def capture_sql(conn, clauseelement, multiparams, params, execution_options):
        statements.append(str(clauseelement))

    try:
        with engine.begin() as connection:
            ingest_module.upsert_photo(
                connection,
                ingest_module.PhotoRecord(
                    photo_id="photo-1",
                    path=path,
                    sha256="b" * 64,
                    filesize=101,
                    ext="jpg",
                    created_ts=now,
                    modified_ts=now + timedelta(minutes=1),
                    shot_ts=None,
                    shot_ts_source=None,
                    camera_make=None,
                    camera_model=None,
                    software=None,
                    orientation=None,
                    gps_latitude=None,
                    gps_longitude=None,
                    gps_altitude=None,
                    thumbnail_jpeg=b"new-thumbnail",
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=80,
                    thumbnail_height=60,
                    faces_count=0,
                ),
            )
    finally:
        event.remove(engine, "before_execute", capture_sql)

    photo = load_photo_row(database_url, path)
    assert photo["thumbnail_jpeg"] == b"new-thumbnail"
    assert photo["thumbnail_width"] == 80
    assert photo["thumbnail_height"] == 60
    thumbnail_selects = [
        statement
        for statement in statements
        if "SELECT" in statement and "thumbnail_jpeg" in statement
    ]
    assert thumbnail_selects == []


def test_photo_is_soft_deleted_only_when_all_file_instances_are_deleted(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'photo-soft-delete.db'}"
    upgrade_database(database_url)
    seed_photo_with_file_instances(database_url)

    now = datetime(2026, 3, 24, tzinfo=UTC)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        touched_photo_ids = reconcile_watched_folder(
            connection,
            watched_folder_id="watched-folder-1",
            observed_relative_paths={"family-events/birthday-park/birthday_park_001.jpg"},
            now=now,
            missing_file_grace_period_days=0,
        )
        refresh_photo_deleted_timestamps(connection, photo_ids=touched_photo_ids, now=now)

    assert load_photo_deleted_ts(database_url, "photo-1") is None

    with engine.begin() as connection:
        touched_photo_ids = reconcile_watched_folder(
            connection,
            watched_folder_id="watched-folder-1",
            observed_relative_paths=set(),
            now=now,
            missing_file_grace_period_days=0,
        )
        refresh_photo_deleted_timestamps(connection, photo_ids=touched_photo_ids, now=now)

    assert load_photo_deleted_ts(database_url, "photo-1") == now


def test_reappearing_file_clears_parent_photo_deleted_timestamp(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'photo-recover.db'}"
    upgrade_database(database_url)
    now = datetime(2026, 3, 24, tzinfo=UTC)
    seed_deleted_photo_with_file_instance(database_url, deleted_ts=now)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        activate_observed_file(
            connection,
            watched_folder_id="watched-folder-1",
            photo_id="photo-1",
            relative_path="family-events/birthday-park/birthday_park_001.jpg",
            filename="birthday_park_001.jpg",
            extension="jpg",
            filesize=100,
            created_ts=now,
            modified_ts=now,
            now=now,
        )
        refresh_photo_deleted_timestamps(connection, photo_ids={"photo-1"}, now=now)

    assert load_photo_deleted_ts(database_url, "photo-1") is None


def load_photo_count(database_url: str) -> int:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(photos)).scalar_one()


def load_photo_row(database_url: str, path: str) -> dict:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        row = connection.execute(
            select(photos).where(photos.c.path == path)
        ).mappings().one()
    payload = dict(row)
    for key in ("created_ts", "modified_ts", "shot_ts", "updated_ts", "deleted_ts", "faces_detected_ts"):
        value = payload.get(key)
        if isinstance(value, datetime) and value.tzinfo is None:
            payload[key] = value.replace(tzinfo=UTC)
    return payload


def load_watched_folder_row(database_url: str, scan_path: str) -> dict:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        row = connection.execute(
            select(watched_folders).where(
                watched_folders.c.scan_path == scan_path
            )
        ).mappings().one()
    payload = dict(row)
    for key in ("created_ts", "updated_ts", "last_successful_scan_ts"):
        value = payload.get(key)
        if isinstance(value, datetime) and value.tzinfo is None:
            payload[key] = value.replace(tzinfo=UTC)
    return payload


def load_watched_folder_by_id(database_url: str, watched_folder_id: str) -> dict:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        row = connection.execute(
            select(watched_folders).where(
                watched_folders.c.watched_folder_id == watched_folder_id
            )
        ).mappings().one()
    payload = dict(row)
    for key in ("created_ts", "updated_ts", "last_successful_scan_ts"):
        value = payload.get(key)
        if isinstance(value, datetime) and value.tzinfo is None:
            payload[key] = value.replace(tzinfo=UTC)
    return payload


def load_pending_queue_count(database_url: str) -> int:
    store = IngestQueueStore(database_url)
    return len(store.list_pending())


def load_pending_queue_rows(database_url: str):
    store = IngestQueueStore(database_url)
    return store.list_pending()


def load_face_count(database_url: str) -> int:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(faces)).scalar_one()


def load_photo_file_row(database_url: str, relative_path: str) -> dict:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        row = connection.execute(
            select(photo_files).where(photo_files.c.relative_path == relative_path)
        ).mappings().one()
    payload = dict(row)
    for key in ("created_ts", "modified_ts", "first_seen_ts", "last_seen_ts", "missing_ts", "deleted_ts"):
        value = payload.get(key)
        if isinstance(value, datetime) and value.tzinfo is None:
            payload[key] = value.replace(tzinfo=UTC)
    return payload


def load_photo_deleted_ts(database_url: str, photo_id: str) -> datetime | None:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        deleted_ts = connection.execute(
            select(photos.c.deleted_ts).where(photos.c.photo_id == photo_id)
        ).scalar_one()
    if isinstance(deleted_ts, datetime) and deleted_ts.tzinfo is None:
        return deleted_ts.replace(tzinfo=UTC)
    return deleted_ts


def load_storage_source_row(database_url: str, storage_source_id: str) -> dict:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        row = connection.execute(
            select(storage_sources).where(storage_sources.c.storage_source_id == storage_source_id)
        ).mappings().one()
    payload = dict(row)
    for key in ("last_validated_ts", "created_ts", "updated_ts"):
        value = payload.get(key)
        if isinstance(value, datetime) and value.tzinfo is None:
            payload[key] = value.replace(tzinfo=UTC)
    return payload


def load_ingest_runs(database_url: str) -> list[dict]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        rows = connection.execute(
            select(ingest_runs).order_by(ingest_runs.c.started_ts, ingest_runs.c.ingest_run_id)
        ).mappings()
    payloads: list[dict] = []
    for row in rows:
        payload = dict(row)
        for key in ("started_ts", "completed_ts"):
            value = payload.get(key)
            if isinstance(value, datetime) and value.tzinfo is None:
                payload[key] = value.replace(tzinfo=UTC)
        payloads.append(payload)
    return payloads


def _source_aware_photo_path(storage_source_id: str, relative_path: str) -> str:
    return posixpath.normpath(
        posixpath.join("/storage-sources", storage_source_id, relative_path)
    )


def seed_linked_storage_source(
    database_url: str,
    *,
    scan_root: Path,
    now: datetime,
) -> str:
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        connection.execute(
            insert(watched_folders).values(
                watched_folder_id=str(
                    uuid5(NAMESPACE_URL, f"watched-folder:{scan_root.resolve().as_posix()}")
                ),
                scan_path=scan_root.resolve().as_posix(),
                storage_source_id=source["storage_source_id"],
                relative_path=".",
                display_name="Family NAS / seed-corpus",
                is_enabled=1,
                availability_state="active",
                last_failure_reason=None,
                last_successful_scan_ts=None,
                created_ts=now,
                updated_ts=now,
            )
        )
    return str(source["storage_source_id"])


def seed_registered_storage_source_with_watched_folder(
    database_url: str,
    *,
    root_path: Path,
    watched_path: Path,
    display_name: str,
    now: datetime,
    alias_paths: tuple[str, ...] | None = None,
) -> tuple[str, str]:
    root = root_path.resolve()
    watched = watched_path.resolve()
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name=display_name,
            marker_filename=MARKER_FILENAME,
            marker_version=1,
            now=now,
        )
        for alias_path in alias_paths or (root.as_posix(),):
            attach_storage_source_alias(
                connection,
                storage_source_id=source["storage_source_id"],
                alias_path=alias_path,
                now=now,
            )
        (root / MARKER_FILENAME).write_text(
            f'{{"storage_source_id":"{source["storage_source_id"]}","marker_version":1}}'
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            watched_path=watched.as_posix(),
            display_name=display_name,
            now=now,
        )
    return str(source["storage_source_id"]), str(watched_folder["watched_folder_id"])


def seed_photo_with_file_instances(database_url: str) -> None:
    now = datetime(2026, 3, 24, tzinfo=UTC)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                path="/test-root/family-events/birthday-park/birthday_park_001.jpg",
                sha256="a" * 64,
                phash=None,
                filesize=100,
                ext="jpg",
                created_ts=now,
                modified_ts=now,
                shot_ts=None,
                shot_ts_source=None,
                camera_make=None,
                camera_model=None,
                software=None,
                orientation=None,
                gps_latitude=None,
                gps_longitude=None,
                gps_altitude=None,
                updated_ts=now,
                deleted_ts=None,
                faces_count=0,
                faces_detected_ts=None,
            )
        )
        connection.execute(
            insert(photo_files),
            [
                {
                    "photo_file_id": "photo-file-1",
                    "photo_id": "photo-1",
                    "watched_folder_id": "watched-folder-1",
                    "relative_path": "family-events/birthday-park/birthday_park_001.jpg",
                    "filename": "birthday_park_001.jpg",
                    "extension": "jpg",
                    "filesize": 100,
                    "created_ts": now,
                    "modified_ts": now,
                    "first_seen_ts": now,
                    "last_seen_ts": now,
                    "missing_ts": None,
                    "deleted_ts": None,
                    "lifecycle_state": "active",
                    "absence_reason": None,
                },
                {
                    "photo_file_id": "photo-file-2",
                    "photo_id": "photo-1",
                    "watched_folder_id": "watched-folder-1",
                    "relative_path": "family-events/birthday-park/birthday_park_002.jpeg",
                    "filename": "birthday_park_002.jpeg",
                    "extension": "jpeg",
                    "filesize": 100,
                    "created_ts": now,
                    "modified_ts": now,
                    "first_seen_ts": now,
                    "last_seen_ts": now,
                    "missing_ts": None,
                    "deleted_ts": None,
                    "lifecycle_state": "active",
                    "absence_reason": None,
                },
            ],
        )


def seed_deleted_photo_with_file_instance(database_url: str, *, deleted_ts: datetime) -> None:
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                path="/test-root/family-events/birthday-park/birthday_park_001.jpg",
                sha256="b" * 64,
                phash=None,
                filesize=100,
                ext="jpg",
                created_ts=deleted_ts,
                modified_ts=deleted_ts,
                shot_ts=None,
                shot_ts_source=None,
                camera_make=None,
                camera_model=None,
                software=None,
                orientation=None,
                gps_latitude=None,
                gps_longitude=None,
                gps_altitude=None,
                updated_ts=deleted_ts,
                deleted_ts=deleted_ts,
                faces_count=0,
                faces_detected_ts=None,
            )
        )
        connection.execute(
            insert(photo_files).values(
                photo_file_id="photo-file-1",
                photo_id="photo-1",
                watched_folder_id="watched-folder-1",
                relative_path="family-events/birthday-park/birthday_park_001.jpg",
                filename="birthday_park_001.jpg",
                extension="jpg",
                filesize=100,
                created_ts=deleted_ts,
                modified_ts=deleted_ts,
                first_seen_ts=deleted_ts,
                last_seen_ts=deleted_ts,
                missing_ts=deleted_ts,
                deleted_ts=deleted_ts,
                lifecycle_state="deleted",
                absence_reason="path_removed",
            )
        )


def _fail_root_scan(_: Path):
    raise PermissionError("root unavailable")


def _create_non_directory_root(tmp_path: Path) -> Path:
    root = tmp_path / "single-file-root.txt"
    root.write_text("not a directory")
    return root


class UnusedFaceDetector:
    def detect(self, path: Path) -> list[dict]:
        raise AssertionError(f"face detector should not be invoked for {path}")
