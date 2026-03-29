from sqlalchemy import create_engine, inspect

from photoorg_db_schema import ingest_queue, ingest_run_files, metadata, storage_source_aliases, storage_sources


def test_phase_zero_schema_exposes_expected_tables():
    expected = {
        "photos",
        "photo_files",
        "faces",
        "people",
        "face_labels",
        "watched_folders",
        "storage_sources",
        "storage_source_aliases",
        "ingest_runs",
        "ingest_queue",
        "ingest_run_files",
    }

    assert expected.issubset(metadata.tables.keys())


def test_ingest_queue_is_publicly_exported_from_shared_schema():
    assert ingest_queue is metadata.tables["ingest_queue"]


def test_ingest_run_files_is_publicly_exported_from_shared_schema():
    assert ingest_run_files is metadata.tables["ingest_run_files"]


def test_storage_source_tables_are_publicly_exported_from_shared_schema():
    assert storage_sources is metadata.tables["storage_sources"]
    assert storage_source_aliases is metadata.tables["storage_source_aliases"]


def test_phase_zero_schema_applies_core_constraints():
    photos = metadata.tables["photos"]
    photo_files = metadata.tables["photo_files"]
    faces = metadata.tables["faces"]
    watched_folders = metadata.tables["watched_folders"]
    storage_sources = metadata.tables["storage_sources"]
    storage_source_aliases = metadata.tables["storage_source_aliases"]
    ingest_queue = metadata.tables["ingest_queue"]
    ingest_run_files = metadata.tables["ingest_run_files"]

    assert photos.c.sha256.unique is True
    assert watched_folders.c.scan_path.unique is True
    assert watched_folders.c.storage_source_id.nullable is True
    assert watched_folders.c.relative_path.nullable is True
    assert [fk.column.table.name for fk in watched_folders.c.storage_source_id.foreign_keys] == [
        "storage_sources"
    ]
    assert storage_sources.c.marker_filename.nullable is False
    assert storage_sources.c.marker_version.nullable is False
    assert str(storage_sources.c.marker_version.server_default.arg) == "1"
    assert str(storage_sources.c.availability_state.server_default.arg) == "'unknown'"
    assert storage_source_aliases.c.alias_path.unique is True
    assert [fk.column.table.name for fk in storage_source_aliases.c.storage_source_id.foreign_keys] == [
        "storage_sources"
    ]
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


def test_storage_source_indexes_are_defined_in_shared_metadata():
    watched_folders = metadata.tables["watched_folders"]
    storage_sources = metadata.tables["storage_sources"]
    storage_source_aliases = metadata.tables["storage_source_aliases"]

    assert {"uq_watched_folders_source_relative_path"} <= {
        constraint.name for constraint in watched_folders.constraints if constraint.name is not None
    }
    assert {"idx_storage_sources_availability_state"} <= {index.name for index in storage_sources.indexes}
    assert {"idx_storage_source_aliases_source_id"} <= {
        index.name for index in storage_source_aliases.indexes
    }

def test_shared_metadata_defines_phase_zero_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schema.db'}", future=True)
    metadata.create_all(engine)

    tables = set(inspect(engine).get_table_names())
    ingest_run_files_indexes = {index["name"] for index in inspect(engine).get_indexes("ingest_run_files")}
    storage_sources_indexes = {index["name"] for index in inspect(engine).get_indexes("storage_sources")}
    storage_source_alias_indexes = {
        index["name"] for index in inspect(engine).get_indexes("storage_source_aliases")
    }

    assert {
        "photos",
        "photo_files",
        "faces",
        "people",
        "face_labels",
        "watched_folders",
        "storage_sources",
        "storage_source_aliases",
        "ingest_runs",
        "ingest_queue",
        "ingest_run_files",
    } <= tables
    assert {
        "idx_ingest_run_files_ingest_run_id",
        "idx_ingest_run_files_ingest_queue_id",
        "idx_ingest_run_files_run_id_outcome",
    } <= ingest_run_files_indexes
    assert {"idx_storage_sources_availability_state"} <= storage_sources_indexes
    assert {"idx_storage_source_aliases_source_id"} <= storage_source_alias_indexes
