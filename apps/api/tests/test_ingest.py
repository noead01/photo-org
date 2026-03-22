from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

from app.migrations import upgrade_database
from app.processing.faces import OpenCvFaceDetector
from app.processing.ingest import ingest_directory
from app.storage import faces, photos



def _resolve_samples_dir() -> Path:
    test_file = Path(__file__).resolve()
    for parent in test_file.parents:
        candidate = parent / "apps" / "api" / "features" / "samples"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not locate apps/api/features/samples from test_ingest.py")


SAMPLES_DIR = _resolve_samples_dir()
PIL = pytest.importorskip("PIL")
pytest.importorskip("pillow_heif")


def test_ingest_directory_loads_sample_photos_into_sqlite(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'photoorg.db'}"
    upgrade_database(db_url)

    result = ingest_directory(SAMPLES_DIR, database_url=db_url)

    assert result.scanned == 10
    assert result.inserted == 10
    assert result.updated == 0
    assert result.errors == []

    engine = create_engine(db_url, future=True)
    with engine.connect() as connection:
        rows = connection.execute(
            select(
                photos.c.path,
                photos.c.ext,
                photos.c.filesize,
                photos.c.sha256,
                photos.c.faces_count,
                photos.c.shot_ts,
                photos.c.shot_ts_source,
                photos.c.camera_make,
                photos.c.camera_model,
                photos.c.gps_latitude,
                photos.c.gps_longitude,
            ).order_by(photos.c.path)
        ).all()

    assert len(rows) == 10
    assert all(row[0].endswith(".HEIC") for row in rows)
    assert all("apps/api/features/samples/" in row[0] for row in rows)
    assert {row[1] for row in rows} == {"heic"}
    assert all(row[2] > 0 for row in rows)
    assert all(len(row[3]) == 64 for row in rows)
    assert all(row[4] == 0 for row in rows)
    sample = next(row for row in rows if row[0].endswith("IMG_3015.HEIC"))
    assert sample[5].isoformat() == "2022-10-08T14:47:12.703000"
    assert sample[6] == "exif:DateTimeOriginal"
    assert sample[7] == "Apple"
    assert sample[8] == "iPhone 12 mini"
    assert sample[9] == pytest.approx(40.0671583, abs=1e-7)
    assert sample[10] == pytest.approx(-82.874, abs=1e-7)


def test_ingest_directory_is_idempotent_for_existing_paths(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'photoorg.db'}"
    upgrade_database(db_url)

    first_run = ingest_directory(SAMPLES_DIR, database_url=db_url)
    second_run = ingest_directory(SAMPLES_DIR, database_url=db_url)

    assert first_run.inserted == 10
    assert second_run.inserted == 0
    assert second_run.updated == 10
    assert second_run.errors == []


def test_ingest_directory_stores_face_rows_when_detector_is_enabled(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'faces.db'}"
    upgrade_database(db_url)

    result = ingest_directory(
        SAMPLES_DIR,
        database_url=db_url,
        face_detector=OpenCvFaceDetector(),
    )

    assert result.errors == []

    engine = create_engine(db_url, future=True)
    with engine.connect() as connection:
        photo_rows = connection.execute(
            select(photos.c.path, photos.c.faces_count).order_by(photos.c.path)
        ).all()
        face_count = connection.execute(select(func.count()).select_from(faces)).scalar_one()
        bitmap_count = connection.execute(
            select(func.count()).select_from(faces).where(faces.c.bitmap.is_not(None))
        ).scalar_one()

    assert face_count > 0
    assert bitmap_count == face_count
    assert sum(row[1] for row in photo_rows) == face_count
    assert any(row[1] > 0 for row in photo_rows)


def test_upgrade_database_creates_search_tables(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'schema.db'}"
    upgrade_database(db_url)
    engine = create_engine(db_url, future=True)

    with engine.connect() as connection:
        tables = set(connection.dialect.get_table_names(connection))

    assert {"photos", "faces", "photo_tags", "people", "face_labels"} <= tables
