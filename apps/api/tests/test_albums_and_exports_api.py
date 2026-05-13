from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, inspect

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import (
    albums,
    editable_album_items,
    photo_files,
    photos,
    saved_filter_album_rules,
    watched_folders,
)


def _client(tmp_path, monkeypatch, filename: str) -> TestClient:
    database_url = f"sqlite:///{tmp_path / filename}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()
    return TestClient(app)


def _seed_photo(connection, *, photo_id: str, relative_path: str, scan_path: str) -> None:
    now = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    watched_folder_id = f"wf-{photo_id}"
    connection.execute(
        insert(photos).values(
            photo_id=photo_id,
            sha256=f"sha256-{photo_id}",
            path=f"/library/{photo_id}.jpg",
            ext="jpg",
            filesize=1024,
            created_ts=now,
            updated_ts=now,
        )
    )
    connection.execute(
        insert(watched_folders).values(
            watched_folder_id=watched_folder_id,
            scan_path=scan_path,
            created_ts=now,
            updated_ts=now,
        )
    )
    connection.execute(
        insert(photo_files).values(
            photo_file_id=f"pf-{photo_id}",
            photo_id=photo_id,
            watched_folder_id=watched_folder_id,
            relative_path=relative_path,
            filename=relative_path.split("/")[-1],
            extension="jpg",
            created_ts=now,
            modified_ts=now,
            last_seen_ts=now,
            lifecycle_state="active",
        )
    )


def test_albums_create_list_and_add_items(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "albums-api.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'albums-api.db'}", future=True)
    with engine.begin() as connection:
            _seed_photo(
                connection,
                photo_id="photo-1",
                relative_path="photo-1.jpg",
                scan_path=str(tmp_path / "wf-1"),
            )
            _seed_photo(
                connection,
                photo_id="photo-2",
                relative_path="photo-2.jpg",
                scan_path=str(tmp_path / "wf-2"),
            )

    create_response = client.post("/api/v1/albums", json={"name": "Weekend Favorites"})
    assert create_response.status_code == 201
    album_id = create_response.json()["album_id"]

    list_response = client.get("/api/v1/albums")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload) == 1
    assert list_payload[0]["name"] == "Weekend Favorites"
    assert list_payload[0]["item_count"] == 0

    add_response = client.post(
        f"/api/v1/albums/{album_id}/items",
        json={"photo_ids": ["photo-1", "photo-2"]},
    )
    assert add_response.status_code == 200
    assert add_response.json() == {
        "album_id": album_id,
        "added_photo_ids": ["photo-1", "photo-2"],
        "duplicate_photo_ids": [],
        "missing_photo_ids": [],
    }

    duplicate_response = client.post(
        f"/api/v1/albums/{album_id}/items",
        json={"photo_ids": ["photo-2", "photo-missing"]},
    )
    assert duplicate_response.status_code == 200
    assert duplicate_response.json() == {
        "album_id": album_id,
        "added_photo_ids": [],
        "duplicate_photo_ids": ["photo-2"],
        "missing_photo_ids": ["photo-missing"],
    }


def test_albums_support_saved_filter_kind_and_reject_duplicate_names(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "albums-kind.db")

    create_editable = client.post(
        "/api/v1/albums",
        json={"name": "Weekend Favorites", "kind": "editable"},
    )
    assert create_editable.status_code == 201
    assert create_editable.json()["kind"] == "editable"

    duplicate_name = client.post(
        "/api/v1/albums",
        json={"name": "weekend favorites", "kind": "editable"},
    )
    assert duplicate_name.status_code == 409
    assert duplicate_name.json()["detail"] == "Album name already exists. Choose a different name."

    create_saved_filter = client.post(
        "/api/v1/albums",
        json={
            "name": "Needs review",
            "kind": "saved_filter",
            "filter_json": {"person_names": ["Inez"], "person_certainty_mode": "human_only"},
        },
    )
    assert create_saved_filter.status_code == 201
    payload = create_saved_filter.json()
    assert payload["kind"] == "saved_filter"
    assert payload["item_count"] == 0
    assert payload["saved_filter"] == {
        "person_names": ["Inez"],
        "person_certainty_mode": "human_only",
    }


def test_albums_detail_patch_delete_and_membership_guards(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "albums-detail.db")
    engine = create_engine(f"sqlite:///{tmp_path / 'albums-detail.db'}", future=True)
    with engine.begin() as connection:
        _seed_photo(
            connection,
            photo_id="photo-1",
            relative_path="photo-1.jpg",
            scan_path=str(tmp_path / "wf-detail"),
        )

    create_editable = client.post(
        "/api/v1/albums",
        json={"name": "Road trip", "kind": "editable"},
    )
    assert create_editable.status_code == 201
    editable_id = create_editable.json()["album_id"]

    add_item = client.post(
        f"/api/v1/albums/{editable_id}/items",
        json={"photo_ids": ["photo-1"]},
    )
    assert add_item.status_code == 200

    detail = client.get(f"/api/v1/albums/{editable_id}")
    assert detail.status_code == 200
    assert detail.json()["album_id"] == editable_id
    assert detail.json()["kind"] == "editable"
    assert detail.json()["items_total"] == 1
    assert [item["photo_id"] for item in detail.json()["items"]] == ["photo-1"]

    rename = client.patch(f"/api/v1/albums/{editable_id}", json={"name": "Road trip 2026"})
    assert rename.status_code == 200
    assert rename.json()["name"] == "Road trip 2026"

    remove_item = client.delete(f"/api/v1/albums/{editable_id}/items/photo-1")
    assert remove_item.status_code == 204

    post_remove_detail = client.get(f"/api/v1/albums/{editable_id}")
    assert post_remove_detail.status_code == 200
    assert post_remove_detail.json()["items_total"] == 0

    create_saved_filter = client.post(
        "/api/v1/albums",
        json={
            "name": "Human confirmed Inez",
            "kind": "saved_filter",
            "filter_json": {"person_names": ["Inez"], "person_certainty_mode": "human_only"},
        },
    )
    assert create_saved_filter.status_code == 201
    saved_filter_id = create_saved_filter.json()["album_id"]

    saved_filter_add_attempt = client.post(
        f"/api/v1/albums/{saved_filter_id}/items",
        json={"photo_ids": ["photo-1"]},
    )
    assert saved_filter_add_attempt.status_code == 409
    assert (
        saved_filter_add_attempt.json()["detail"]
        == "Saved-filter albums cannot be modified directly."
    )

    saved_filter_remove_attempt = client.delete(
        f"/api/v1/albums/{saved_filter_id}/items/photo-1"
    )
    assert saved_filter_remove_attempt.status_code == 409
    assert (
        saved_filter_remove_attempt.json()["detail"]
        == "Saved-filter albums cannot be modified directly."
    )

    delete_album = client.delete(f"/api/v1/albums/{editable_id}")
    assert delete_album.status_code == 204

    deleted_lookup = client.get(f"/api/v1/albums/{editable_id}")
    assert deleted_lookup.status_code == 404
    assert deleted_lookup.json()["detail"] == "Album not found"


def test_photo_export_returns_zip_with_selected_files(tmp_path, monkeypatch):
    source_root = tmp_path / "exports"
    source_root.mkdir(parents=True, exist_ok=True)
    folder_a = source_root / "a"
    folder_b = source_root / "b"
    folder_c = source_root / "c"
    folder_a.mkdir(parents=True, exist_ok=True)
    folder_b.mkdir(parents=True, exist_ok=True)
    folder_c.mkdir(parents=True, exist_ok=True)
    file_a = folder_a / "trip-a.jpg"
    file_b = folder_b / "trip-b.jpg"
    file_c = folder_c / "portrait.heic"
    file_a.write_bytes(b"trip-a-bytes")
    file_b.write_bytes(b"trip-b-bytes")
    file_c.write_bytes(b"heic-original-binary-payload")

    client = _client(tmp_path, monkeypatch, "exports-api.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'exports-api.db'}", future=True)
    with engine.begin() as connection:
        _seed_photo(connection, photo_id="photo-a", relative_path="trip-a.jpg", scan_path=str(folder_a))
        _seed_photo(connection, photo_id="photo-b", relative_path="trip-b.jpg", scan_path=str(folder_b))
        _seed_photo(connection, photo_id="photo-c", relative_path="portrait.heic", scan_path=str(folder_c))

    response = client.post(
        "/api/v1/exports/photos",
        json={"photo_ids": ["photo-a", "photo-missing", "photo-c", "photo-b"]},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["x-photo-org-exported-count"] == "3"
    assert response.headers["x-photo-org-skipped-count"] == "1"

    archive = ZipFile(BytesIO(response.content))
    names = sorted(archive.namelist())
    assert names == ["photo-a-trip-a.jpg", "photo-b-trip-b.jpg", "photo-c-portrait.heic"]
    assert archive.read("photo-a-trip-a.jpg") == b"trip-a-bytes"
    assert archive.read("photo-b-trip-b.jpg") == b"trip-b-bytes"
    assert archive.read("photo-c-portrait.heic") == b"heic-original-binary-payload"


def test_photo_export_rejects_empty_photo_ids(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "exports-empty.db")

    response = client.post("/api/v1/exports/photos", json={"photo_ids": []})

    assert response.status_code == 422


def test_migration_creates_album_tables(tmp_path):
    from app.migrations import upgrade_database

    database_url = f"sqlite:///{tmp_path / 'albums-schema.db'}"
    upgrade_database(database_url)

    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        inspector = inspect(connection)
        album_columns = {column["name"] for column in inspector.get_columns(albums.name)}
        item_columns = {column["name"] for column in inspector.get_columns(editable_album_items.name)}
        rule_columns = {column["name"] for column in inspector.get_columns(saved_filter_album_rules.name)}

    assert {"album_id", "name", "owner_user_id", "kind", "created_ts", "updated_ts"} <= album_columns
    assert {"album_id", "photo_id", "added_by_user_id", "added_ts"} <= item_columns
    assert {"album_id", "filter_json", "updated_ts"} <= rule_columns
