from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select

from app.migrations import upgrade_database


def test_storage_source_repository_persists_sources_aliases_and_availability(tmp_path):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
        get_storage_source_by_marker_id,
        list_storage_source_aliases,
        update_storage_source_availability,
    )

    database_url = f"sqlite:///{tmp_path / 'storage-sources.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 18, 0, tzinfo=UTC)

    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        alias = attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path="//nas/family",
            now=now,
        )
        update_storage_source_availability(
            connection,
            storage_source_id=source["storage_source_id"],
            availability_state="active",
            last_failure_reason=None,
            now=now,
        )
        loaded = get_storage_source_by_marker_id(connection, source["storage_source_id"])
        aliases = list_storage_source_aliases(connection, source["storage_source_id"])

    assert alias["alias_path"] == "//nas/family"
    assert loaded is not None
    assert loaded["display_name"] == "Family NAS"
    assert loaded["availability_state"] == "active"
    assert [row["alias_path"] for row in aliases] == [alias["alias_path"]]
    assert [row["storage_source_id"] for row in aliases] == [source["storage_source_id"]]


def test_storage_source_alias_rejects_conflict_with_different_source(tmp_path):
    from app.services.storage_sources import (
        StorageSourceConflictError,
        attach_storage_source_alias,
        create_storage_source,
    )

    database_url = f"sqlite:///{tmp_path / 'storage-sources-conflict.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 18, 30, tzinfo=UTC)

    with engine.begin() as connection:
        source_a = create_storage_source(
            connection,
            display_name="Family NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        source_b = create_storage_source(
            connection,
            display_name="Travel Drive",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source_a["storage_source_id"],
            alias_path="//nas/family",
            now=now,
        )

        try:
            attach_storage_source_alias(
                connection,
                storage_source_id=source_b["storage_source_id"],
                alias_path="//nas/family",
                now=now,
            )
        except StorageSourceConflictError as exc:
            assert "already belongs to storage_source_id" in str(exc)
        else:
            raise AssertionError("expected alias conflict")
