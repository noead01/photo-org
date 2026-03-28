from sqlalchemy import create_engine, inspect

from photoorg_db_schema import ingest_queue, ingest_run_files, metadata


def test_phase_zero_schema_exposes_expected_tables():
    expected = {
        "photos",
        "photo_files",
        "faces",
        "people",
        "face_labels",
        "watched_folders",
        "ingest_runs",
        "ingest_queue",
        "ingest_run_files",
    }

    assert expected.issubset(metadata.tables.keys())


def test_ingest_queue_is_publicly_exported_from_shared_schema():
    assert ingest_queue is metadata.tables["ingest_queue"]


def test_ingest_run_files_is_publicly_exported_from_shared_schema():
    assert ingest_run_files is metadata.tables["ingest_run_files"]


def test_phase_zero_schema_applies_core_constraints():
    photos = metadata.tables["photos"]
    photo_files = metadata.tables["photo_files"]
    faces = metadata.tables["faces"]
    watched_folders = metadata.tables["watched_folders"]
    ingest_queue = metadata.tables["ingest_queue"]
    ingest_run_files = metadata.tables["ingest_run_files"]

    assert photos.c.sha256.unique is True
    assert watched_folders.c.scan_path.unique is True
    assert watched_folders.c.container_mount_path.unique is True
    assert [fk.column.table.name for fk in photo_files.c.photo_id.foreign_keys] == ["photos"]
    assert [fk.column.table.name for fk in faces.c.photo_id.foreign_keys] == ["photos"]
    assert ingest_queue.c.idempotency_key.unique is True
    assert str(ingest_queue.c.status.server_default.arg) == "'pending'"
    assert str(ingest_queue.c.attempt_count.server_default.arg) == "0"
    assert [fk.column.table.name for fk in ingest_run_files.c.ingest_run_id.foreign_keys] == [
        "ingest_runs"
    ]
    assert [fk.column.table.name for fk in ingest_run_files.c.ingest_queue_id.foreign_keys] == [
        "ingest_queue"
    ]
    assert ingest_run_files.c.ingest_queue_id.nullable is False
    assert [fk.ondelete for fk in ingest_run_files.c.ingest_queue_id.foreign_keys] == ["CASCADE"]


def test_ingest_run_files_indexes_are_defined_in_shared_metadata():
    ingest_run_files = metadata.tables["ingest_run_files"]

    assert {
        "idx_ingest_run_files_ingest_run_id",
        "idx_ingest_run_files_ingest_queue_id",
        "idx_ingest_run_files_run_id_outcome",
    } <= {index.name for index in ingest_run_files.indexes}

def test_shared_metadata_defines_phase_zero_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schema.db'}", future=True)
    metadata.create_all(engine)

    tables = set(inspect(engine).get_table_names())
    ingest_run_files_indexes = {index["name"] for index in inspect(engine).get_indexes("ingest_run_files")}

    assert {
        "photos",
        "photo_files",
        "faces",
        "people",
        "face_labels",
        "watched_folders",
        "ingest_runs",
        "ingest_queue",
        "ingest_run_files",
    } <= tables
    assert {
        "idx_ingest_run_files_ingest_run_id",
        "idx_ingest_run_files_ingest_queue_id",
        "idx_ingest_run_files_run_id_outcome",
    } <= ingest_run_files_indexes
