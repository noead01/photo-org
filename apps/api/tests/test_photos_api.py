from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, update
from sqlalchemy.orm import Session

from app.dependencies import _get_session_factory, get_db
from app.main import app
from app.migrations import upgrade_database
from app.storage import photos


def test_photo_listing_api_returns_photos_in_deterministic_order(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photos-api.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    same_ts = datetime(2026, 3, 28, 19, 30)
    later_ts = datetime(2026, 3, 29, 9, 15)
    deleted_ts = datetime(2026, 3, 29, 10, 0)

    with engine.begin() as connection:
        connection.execute(
            insert(photos),
            [
                {
                    "photo_id": "photo-b",
                    "sha256": "b" * 64,
                    "path": "/library/b.jpg",
                    "shot_ts": same_ts,
                    "created_ts": same_ts,
                    "updated_ts": same_ts,
                    "ext": "jpg",
                    "filesize": 111,
                },
                {
                    "photo_id": "photo-c",
                    "sha256": "c" * 64,
                    "path": "/library/c.jpg",
                    "shot_ts": same_ts,
                    "created_ts": same_ts,
                    "updated_ts": same_ts,
                    "ext": "jpg",
                    "filesize": 222,
                },
                {
                    "photo_id": "photo-a",
                    "sha256": "a" * 64,
                    "path": "/library/a.jpg",
                    "shot_ts": later_ts,
                    "created_ts": later_ts,
                    "updated_ts": later_ts,
                    "ext": "jpg",
                    "filesize": 333,
                },
                {
                    "photo_id": "photo-deleted",
                    "sha256": "d" * 64,
                    "path": "/library/deleted.jpg",
                    "shot_ts": deleted_ts,
                    "created_ts": deleted_ts,
                    "updated_ts": deleted_ts,
                    "ext": "jpg",
                    "filesize": 444,
                },
            ],
        )
        connection.execute(
            update(photos)
            .where(photos.c.photo_id == "photo-deleted")
            .values(deleted_ts=deleted_ts)
        )

    session_factory = _get_session_factory(database_url)

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.get("/api/v1/photos")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()

    assert [row["photo_id"] for row in payload] == ["photo-a", "photo-c", "photo-b"]
    assert all(row["photo_id"] != "photo-deleted" for row in payload)
    assert [row["shot_ts"] for row in payload] == [
        "2026-03-29T09:15:00Z",
        "2026-03-28T19:30:00Z",
        "2026-03-28T19:30:00Z",
    ]


def test_photo_listing_api_allows_missing_shot_timestamp_and_sorts_it_last(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photos-api-null-shot-ts.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    known_ts = datetime(2026, 3, 29, 9, 15)

    with engine.begin() as connection:
        connection.execute(
            insert(photos),
            [
                {
                    "photo_id": "photo-with-shot-ts",
                    "sha256": "a" * 64,
                    "path": "/library/with-shot-ts.jpg",
                    "shot_ts": known_ts,
                    "created_ts": known_ts,
                    "updated_ts": known_ts,
                    "ext": "jpg",
                    "filesize": 333,
                },
                {
                    "photo_id": "photo-without-shot-ts",
                    "sha256": "b" * 64,
                    "path": "/library/without-shot-ts.jpg",
                    "shot_ts": None,
                    "created_ts": known_ts,
                    "updated_ts": known_ts,
                    "ext": "jpg",
                    "filesize": 222,
                },
            ],
        )

    session_factory = _get_session_factory(database_url)

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.get("/api/v1/photos")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert [row["photo_id"] for row in payload] == ["photo-with-shot-ts", "photo-without-shot-ts"]
    assert [row["shot_ts"] for row in payload] == ["2026-03-29T09:15:00Z", None]
