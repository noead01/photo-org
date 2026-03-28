from datetime import UTC, datetime, timedelta
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, insert, select

from app.db.queue import IngestQueueStore
from app.migrations import upgrade_database
from app.processing import ingest as ingest_module
from app.processing.ingest import ingest_directory, reconcile_directory
from app.services.file_reconciliation import (
    activate_observed_file,
    reconcile_watched_folder,
    refresh_photo_deleted_timestamps,
)
from app.storage import faces, photo_files, photos, watched_folders


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
SEED_CORPUS_CONTAINER_PATH = "/photos/seed-corpus"
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
    )

    assert result.scanned == 6
    assert result.enqueued == 6
    assert result.inserted == 0
    assert result.updated == 0
    assert result.errors == []

    rows = load_pending_queue_rows(db_url)

    assert len(rows) == 6
    assert all(row.payload_type == "photo_metadata" for row in rows)
    assert all(row.payload_json["path"].startswith(f"{SEED_CORPUS_CONTAINER_PATH}/") for row in rows)
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
    )
    second_run = ingest_directory(
        staged_corpus_dir,
        database_url=db_url,
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
    )

    missing_path = staged_corpus_dir / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    missing_path.unlink()

    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
    )

    row = load_photo_file_row(db_url, "family-events/birthday-park/birthday_park_006.jpg")
    assert row["lifecycle_state"] == "missing"
    assert row["missing_ts"] is not None
    assert row["deleted_ts"] is None

    watched_folder = load_watched_folder_row(db_url, SEED_CORPUS_CONTAINER_PATH)
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=now,
    )

    missing_path = staged_corpus_dir / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    missing_path.unlink()

    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=now,
    )
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=now + timedelta(days=1, seconds=1),
    )

    row = load_photo_file_row(
        db_url,
        "family-events/birthday-park/birthday_park_006.jpg",
    )
    assert row["lifecycle_state"] == "deleted"
    assert row["missing_ts"] == now
    assert row["deleted_ts"] == now + timedelta(days=1, seconds=1)

    watched_folder = load_watched_folder_row(db_url, SEED_CORPUS_CONTAINER_PATH)
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=now,
        missing_file_grace_period_days=0,
    )

    missing_path = staged_corpus_dir / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    missing_path.unlink()

    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
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

    watched_folder = load_watched_folder_row(db_url, SEED_CORPUS_CONTAINER_PATH)
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=healthy_now,
    )

    watched_folder = load_watched_folder_row(db_url, SEED_CORPUS_CONTAINER_PATH)
    assert watched_folder["availability_state"] == "active"
    assert watched_folder["last_failure_reason"] is None
    assert watched_folder["last_successful_scan_ts"] == healthy_now

    monkeypatch.setattr("app.processing.ingest.iter_photo_files", _fail_root_scan)

    failure_now = healthy_now + timedelta(minutes=1)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=failure_now,
    )

    row = load_watched_folder_row(db_url, SEED_CORPUS_CONTAINER_PATH)
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=healthy_now,
    )

    monkeypatch.setattr("app.processing.ingest.iter_photo_files", _fail_root_scan)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=failure_now,
    )

    row = load_watched_folder_row(db_url, SEED_CORPUS_CONTAINER_PATH)
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=now,
    )

    missing_path = staged_corpus_dir / "family-events" / "birthday-park" / "birthday_park_006.jpg"
    missing_path.unlink()

    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=now,
    )
    deleted_now = now + timedelta(days=1, seconds=1)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=healthy_now,
    )

    original_iter_photo_files = ingest_module.iter_photo_files
    monkeypatch.setattr("app.processing.ingest.iter_photo_files", _fail_root_scan)

    failure_now = healthy_now + timedelta(minutes=1)
    reconcile_directory(
        staged_corpus_dir,
        database_url=db_url,
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
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
        container_mount_path=SEED_CORPUS_CONTAINER_PATH,
        now=recovered_now,
    )

    row = load_watched_folder_row(db_url, SEED_CORPUS_CONTAINER_PATH)
    assert row["availability_state"] == "active"
    assert row["last_failure_reason"] is None
    assert row["last_successful_scan_ts"] == recovered_now


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


def load_watched_folder_row(database_url: str, container_mount_path: str) -> dict:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        row = connection.execute(
            select(watched_folders).where(
                watched_folders.c.container_mount_path == container_mount_path
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


def seed_photo_with_file_instances(database_url: str) -> None:
    now = datetime(2026, 3, 24, tzinfo=UTC)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                path=f"{SEED_CORPUS_CONTAINER_PATH}/family-events/birthday-park/birthday_park_001.jpg",
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
                path=f"{SEED_CORPUS_CONTAINER_PATH}/family-events/birthday-park/birthday_park_001.jpg",
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
