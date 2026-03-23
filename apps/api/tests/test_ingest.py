from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

from app.db.queue import IngestQueueStore
from app.migrations import upgrade_database
from app.processing.ingest import ingest_directory
from app.storage import faces, photos



def _resolve_samples_dir() -> Path:
    test_file = Path(__file__).resolve()
    for parent in test_file.parents:
        candidate = parent / "apps" / "api" / "tests" / "fixtures" / "samples"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not locate apps/api/tests/fixtures/samples from test_ingest.py")


SAMPLES_DIR = _resolve_samples_dir()
PIL = pytest.importorskip("PIL")
pytest.importorskip("pillow_heif")


def test_ingest_directory_loads_sample_photos_into_queue(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'photoorg.db'}"
    upgrade_database(db_url)
    trigger_client = RecordingTriggerClient()

    result = ingest_directory(
        SAMPLES_DIR,
        database_url=db_url,
        trigger_client=trigger_client,
    )

    assert result.scanned == 10
    assert result.enqueued == 10
    assert result.inserted == 0
    assert result.updated == 0
    assert result.errors == []
    assert trigger_client.calls == 1

    rows = load_pending_queue_rows(db_url)

    assert len(rows) == 10
    assert all(row.payload_type == "photo_metadata" for row in rows)
    assert all(row.payload_json["path"].endswith(".HEIC") for row in rows)
    assert all("apps/api/tests/fixtures/samples/" in row.payload_json["path"] for row in rows)
    assert {row.payload_json["ext"] for row in rows} == {"heic"}
    assert all(row.payload_json["filesize"] > 0 for row in rows)
    assert all(len(row.payload_json["sha256"]) == 64 for row in rows)
    assert all(row.payload_json["faces_count"] == 0 for row in rows)
    sample = next(row for row in rows if row.payload_json["path"].endswith("IMG_3015.HEIC"))
    assert sample.payload_json["shot_ts"] == "2022-10-08T14:47:12.703000-04:00"
    assert sample.payload_json["shot_ts_source"] == "exif:DateTimeOriginal"
    assert sample.payload_json["camera_make"] == "Apple"
    assert sample.payload_json["camera_model"] == "iPhone 12 mini"
    assert sample.payload_json["gps_latitude"] == pytest.approx(40.0671583, abs=1e-7)
    assert sample.payload_json["gps_longitude"] == pytest.approx(-82.874, abs=1e-7)
    assert load_photo_count(db_url) == 0


def test_ingest_directory_enqueues_records_without_writing_photos_table(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'queue-ingest.db'}"
    upgrade_database(db_url)
    trigger_client = RecordingTriggerClient()

    result = ingest_directory(
        SAMPLES_DIR,
        database_url=db_url,
        queue_commit_chunk_size=1000,
        trigger_client=trigger_client,
    )

    assert result.scanned == 10
    assert result.enqueued == 10
    assert load_photo_count(db_url) == 0
    assert load_pending_queue_count(db_url) == 10
    assert trigger_client.calls == 1


def test_ingest_directory_is_idempotent_for_existing_paths(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'photoorg.db'}"
    upgrade_database(db_url)
    trigger_client = RecordingTriggerClient()

    first_run = ingest_directory(SAMPLES_DIR, database_url=db_url, trigger_client=trigger_client)
    second_run = ingest_directory(SAMPLES_DIR, database_url=db_url, trigger_client=trigger_client)

    assert first_run.enqueued == 10
    assert second_run.enqueued == 10
    assert second_run.inserted == 0
    assert second_run.updated == 0
    assert second_run.errors == []
    assert load_photo_count(db_url) == 0
    assert load_pending_queue_count(db_url) == 10
    assert trigger_client.calls == 2


def test_ingest_directory_keeps_domain_tables_unwritten_when_detector_is_enabled(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'faces.db'}"
    upgrade_database(db_url)
    trigger_client = RecordingTriggerClient()

    result = ingest_directory(
        SAMPLES_DIR,
        database_url=db_url,
        trigger_client=trigger_client,
        face_detector=UnusedFaceDetector(),
    )

    assert result.errors == []
    assert result.enqueued == 10
    assert load_photo_count(db_url) == 0
    assert load_face_count(db_url) == 0
    assert load_pending_queue_count(db_url) == 10
    assert trigger_client.calls == 1


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


class RecordingTriggerClient:
    def __init__(self) -> None:
        self.calls = 0

    def process_pending_queue(self) -> None:
        self.calls += 1


class UnusedFaceDetector:
    def detect(self, path: Path) -> list[dict]:
        raise AssertionError(f"face detector should not be invoked for {path}")
