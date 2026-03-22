from sqlalchemy import create_engine, inspect

from app.storage import ensure_schema
from photoorg_db_schema import metadata


def test_phase_zero_schema_exposes_expected_tables():
    expected = {
        "photos",
        "photo_files",
        "faces",
        "people",
        "face_labels",
        "watched_folders",
        "ingest_runs",
    }

    assert expected.issubset(metadata.tables.keys())

def test_phase_zero_schema_applies_core_constraints():
    photos = metadata.tables["photos"]
    photo_files = metadata.tables["photo_files"]
    faces = metadata.tables["faces"]
    watched_folders = metadata.tables["watched_folders"]
    ingest_queue = metadata.tables["ingest_queue"]

    assert photos.c.sha256.unique is True
    assert watched_folders.c.root_path.unique is True
    assert [fk.column.table.name for fk in photo_files.c.photo_id.foreign_keys] == ["photos"]
    assert [fk.column.table.name for fk in faces.c.photo_id.foreign_keys] == ["photos"]
    assert ingest_queue.c.idempotency_key.unique is True
    assert str(ingest_queue.c.status.server_default.arg) == "'pending'"
    assert str(ingest_queue.c.attempt_count.server_default.arg) == "0"


def test_ensure_schema_creates_phase_zero_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schema.db'}", future=True)
    ensure_schema(engine)

    tables = set(inspect(engine).get_table_names())

    assert {
        "photos",
        "photo_files",
        "faces",
        "people",
        "face_labels",
        "watched_folders",
        "ingest_runs",
    } <= tables
