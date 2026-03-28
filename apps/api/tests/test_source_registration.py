from __future__ import annotations

import json

from sqlalchemy import create_engine, select

from app.migrations import upgrade_database
from app.storage import storage_source_aliases, storage_sources


def test_register_storage_source_creates_marker_and_alias_record(tmp_path):
    from app.services.source_registration import MARKER_FILENAME, register_storage_source

    database_url = f"sqlite:///{tmp_path / 'register-source.db'}"
    upgrade_database(database_url)
    root = tmp_path / "family-share"
    root.mkdir()

    registered = register_storage_source(
        database_url=database_url,
        root_path=root,
        alias_path="//nas/family-share",
        display_name="Family Share",
    )

    marker_path = root / MARKER_FILENAME

    assert registered["display_name"] == "Family Share"
    assert marker_path.is_file()

    marker = json.loads(marker_path.read_text())

    assert marker == {
        "storage_source_id": registered["storage_source_id"],
        "marker_version": 1,
    }

    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        source_row = connection.execute(
            select(storage_sources).where(
                storage_sources.c.storage_source_id == registered["storage_source_id"]
            )
        ).mappings().one()
        alias_rows = connection.execute(
            select(storage_source_aliases).where(
                storage_source_aliases.c.storage_source_id == registered["storage_source_id"]
            )
        ).mappings().all()

    assert source_row["display_name"] == "Family Share"
    assert alias_rows[0]["alias_path"] == "//nas/family-share"


def test_register_storage_source_reuses_existing_source_when_marker_matches(tmp_path):
    from app.services.source_registration import register_storage_source

    database_url = f"sqlite:///{tmp_path / 'register-source-existing.db'}"
    upgrade_database(database_url)
    root = tmp_path / "family-share"
    root.mkdir()

    first = register_storage_source(
        database_url=database_url,
        root_path=root,
        alias_path="//nas/family-share",
        display_name="Family Share",
    )
    second = register_storage_source(
        database_url=database_url,
        root_path=root,
        alias_path="smb://family.local/family-share",
        display_name="Ignored Alias Name",
    )

    assert second["storage_source_id"] == first["storage_source_id"]

    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        alias_rows = connection.execute(
            select(storage_source_aliases.c.alias_path).where(
                storage_source_aliases.c.storage_source_id == first["storage_source_id"]
            )
        ).scalars().all()

    assert alias_rows == ["//nas/family-share", "smb://family.local/family-share"]


def test_register_storage_source_rejects_unknown_marker_identity(tmp_path):
    from app.services.source_registration import MARKER_FILENAME, SourceRegistrationError, register_storage_source

    database_url = f"sqlite:///{tmp_path / 'register-source-conflict.db'}"
    upgrade_database(database_url)
    root = tmp_path / "family-share"
    root.mkdir()
    (root / MARKER_FILENAME).write_text(
        json.dumps({"storage_source_id": "missing-source-id", "marker_version": 1})
    )

    try:
        register_storage_source(
            database_url=database_url,
            root_path=root,
            alias_path="//nas/family-share",
            display_name="Family Share",
        )
    except SourceRegistrationError as exc:
        assert "unknown storage source" in str(exc)
    else:
        raise AssertionError("expected unknown marker identity failure")
