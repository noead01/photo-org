import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

from app.db.queue import IngestQueueStore
from app.migrations import upgrade_database
from app.processing.ingest import ingest_directory
from app.storage import faces, photos


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
    assert all("seed-corpus/family-events/birthday-park/" in row.payload_json["path"] for row in rows)
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

    first_run = ingest_directory(staged_corpus_dir, database_url=db_url)
    second_run = ingest_directory(staged_corpus_dir, database_url=db_url)

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


def load_photo_count(database_url: str) -> int:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(photos)).scalar_one()


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


class UnusedFaceDetector:
    def detect(self, path: Path) -> list[dict]:
        raise AssertionError(f"face detector should not be invoked for {path}")
