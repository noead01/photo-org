from pathlib import Path
from sqlalchemy import create_engine, inspect, select

from app.processing.ingest import ingest_directory
from app.storage import photos


SAMPLES_DIR = Path("/mnt/d/Projects/photo-org/apps/api/features/samples")


def test_upgrade_database_creates_schema(tmp_path):
    from app.migrations import upgrade_database

    database_url = f"sqlite:///{tmp_path / 'migrated.db'}"

    upgrade_database(database_url)

    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())

    assert {"photos", "faces", "photo_tags", "people", "face_labels"} <= tables


def test_upgrade_database_creates_ingest_queue_table(tmp_path):
    from app.migrations import upgrade_database

    database_url = f"sqlite:///{tmp_path / 'queue.db'}"

    upgrade_database(database_url)

    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        tables = set(connection.dialect.get_table_names(connection))

    assert "ingest_queue" in tables


def test_ingest_requires_existing_schema(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'missing-schema.db'}"

    result = ingest_directory(SAMPLES_DIR, database_url=database_url)

    assert result.errors
    assert "no such table: photos" in result.errors[0]


def test_ingest_succeeds_after_running_migrations(tmp_path):
    from app.migrations import upgrade_database

    database_url = f"sqlite:///{tmp_path / 'ingest.db'}"
    upgrade_database(database_url)

    result = ingest_directory(SAMPLES_DIR, database_url=database_url)

    assert result.errors == []

    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        count = connection.execute(select(photos.c.photo_id)).all()

    assert len(count) == 10
