from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, select

from app.migrations import upgrade_database
from app.storage import watched_folders


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


def test_create_watched_folder_persists_source_relative_path(tmp_path):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
    )
    from app.services.watched_folders import create_watched_folder, list_watched_folders

    database_url = f"sqlite:///{tmp_path / 'watched-folders.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 0, tzinfo=UTC)

    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path="//nas/family",
            now=now,
        )

        created = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path="//nas/family",
            watched_path="//nas/family/2024/trips",
            display_name="Trips",
            now=now,
        )
        rows = list_watched_folders(connection, source["storage_source_id"])
        row = connection.execute(
            select(watched_folders).where(
                watched_folders.c.watched_folder_id == created["watched_folder_id"]
            )
        ).mappings().one()

    assert created["storage_source_id"] == source["storage_source_id"]
    assert created["watched_folder_id"] == str(
        uuid5(NAMESPACE_URL, "watched-folder://nas/family/2024/trips")
    )
    assert created["relative_path"] == "2024/trips"
    assert created["scan_path"] == "//nas/family/2024/trips"
    assert created["container_mount_path"] == "//nas/family/2024/trips"
    assert [entry["relative_path"] for entry in rows] == ["2024/trips"]
    assert row["display_name"] == "Trips"
    assert row["is_enabled"] == 1


def test_create_watched_folder_rejects_path_outside_source_boundary(tmp_path):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
    )
    from app.services.watched_folders import WatchedFolderValidationError, create_watched_folder

    database_url = f"sqlite:///{tmp_path / 'watched-folder-boundary.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 5, tzinfo=UTC)

    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path="//nas/family",
            now=now,
        )

        try:
            create_watched_folder(
                connection,
                storage_source_id=source["storage_source_id"],
                alias_path="//nas/family",
                watched_path="//nas/other/trips",
                display_name="Trips",
                now=now,
            )
        except WatchedFolderValidationError as exc:
            assert "outside source boundary" in str(exc)
        else:
            raise AssertionError("expected watched-folder boundary failure")


def test_create_watched_folder_rejects_parent_directory_escape(tmp_path):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
    )
    from app.services.watched_folders import WatchedFolderValidationError, create_watched_folder

    database_url = f"sqlite:///{tmp_path / 'watched-folder-parent-escape.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 7, tzinfo=UTC)

    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path="//nas/family",
            now=now,
        )

        try:
            create_watched_folder(
                connection,
                storage_source_id=source["storage_source_id"],
                alias_path="//nas/family",
                watched_path="//nas/family/../other",
                display_name="Trips",
                now=now,
            )
        except WatchedFolderValidationError as exc:
            assert "outside source boundary" in str(exc) or "must not contain '..'" in str(exc)
        else:
            raise AssertionError("expected parent-directory rejection")


def test_disable_enable_and_remove_watched_folder(tmp_path):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
    )
    from app.services.watched_folders import (
        create_watched_folder,
        list_watched_folders,
        remove_watched_folder,
        set_watched_folder_enabled,
    )

    database_url = f"sqlite:///{tmp_path / 'watched-folder-flags.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 10, tzinfo=UTC)

    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path="//nas/family",
            now=now,
        )
        created = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path="//nas/family",
            watched_path="//nas/family/2024/trips",
            display_name="Trips",
            now=now,
        )

        disabled = set_watched_folder_enabled(
            connection,
            storage_source_id=source["storage_source_id"],
            watched_folder_id=created["watched_folder_id"],
            is_enabled=False,
            now=now,
        )
        enabled = set_watched_folder_enabled(
            connection,
            storage_source_id=source["storage_source_id"],
            watched_folder_id=created["watched_folder_id"],
            is_enabled=True,
            now=now,
        )
        remove_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            watched_folder_id=created["watched_folder_id"],
        )
        remaining = list_watched_folders(connection, source["storage_source_id"])

    assert disabled["is_enabled"] == 0
    assert enabled["is_enabled"] == 1
    assert remaining == []
