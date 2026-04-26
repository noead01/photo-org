from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import faces, people, photos
from photoorg_db_schema import EMBEDDING_DIMENSION


def _client(tmp_path, monkeypatch, filename: str) -> TestClient:
    database_url = f"sqlite:///{tmp_path / filename}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()
    return TestClient(app)


def _insert_photo(connection, *, photo_id: str) -> None:
    now = datetime(2026, 4, 26, 12, 0, tzinfo=UTC)
    connection.execute(
        insert(photos).values(
            photo_id=photo_id,
            sha256=f"sha256-{photo_id}",
            created_ts=now,
            updated_ts=now,
        )
    )


def _insert_person(connection, *, person_id: str, display_name: str) -> None:
    now = datetime(2026, 4, 26, 12, 0, tzinfo=UTC)
    connection.execute(
        insert(people).values(
            person_id=person_id,
            display_name=display_name,
            created_ts=now,
            updated_ts=now,
        )
    )


def _embedding(first: float, second: float) -> list[float]:
    values = [0.0] * EMBEDDING_DIMENSION
    values[0] = first
    values[1] = second
    return values


def test_face_candidates_api_returns_ranked_person_candidates_with_per_person_best_match(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path, monkeypatch, "face-candidates-ranked.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'face-candidates-ranked.db'}", future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_photo(connection, photo_id="photo-2")
        _insert_person(connection, person_id="person-1", display_name="Alex")
        _insert_person(connection, person_id="person-2", display_name="Blair")
        _insert_person(connection, person_id="person-3", display_name="Casey")
        connection.execute(
            insert(faces),
            [
                {
                    "face_id": "source-face",
                    "photo_id": "photo-1",
                    "person_id": None,
                    "embedding": _embedding(1.0, 0.0),
                },
                {
                    "face_id": "candidate-1-best",
                    "photo_id": "photo-2",
                    "person_id": "person-1",
                    "embedding": _embedding(0.99, 0.01),
                },
                {
                    "face_id": "candidate-1-worse",
                    "photo_id": "photo-2",
                    "person_id": "person-1",
                    "embedding": _embedding(0.8, 0.2),
                },
                {
                    "face_id": "candidate-2",
                    "photo_id": "photo-2",
                    "person_id": "person-2",
                    "embedding": _embedding(0.8, 0.6),
                },
                {
                    "face_id": "candidate-3",
                    "photo_id": "photo-2",
                    "person_id": "person-3",
                    "embedding": _embedding(0.0, 1.0),
                },
                {
                    "face_id": "unlabeled-face",
                    "photo_id": "photo-2",
                    "person_id": None,
                    "embedding": _embedding(0.999, 0.001),
                },
            ],
        )

    response = client.get("/api/v1/faces/source-face/candidates", params={"limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["face_id"] == "source-face"
    assert [candidate["person_id"] for candidate in payload["candidates"]] == [
        "person-1",
        "person-2",
    ]
    assert [candidate["matched_face_id"] for candidate in payload["candidates"]] == [
        "candidate-1-best",
        "candidate-2",
    ]
    assert [candidate["display_name"] for candidate in payload["candidates"]] == [
        "Alex",
        "Blair",
    ]
    assert payload["candidates"][0]["distance"] == pytest.approx(0.000051, abs=1e-4)
    assert payload["candidates"][1]["distance"] == pytest.approx(0.2, abs=1e-6)


def test_face_candidates_api_returns_404_for_missing_face(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "face-candidates-missing-face.db")

    response = client.get("/api/v1/faces/missing-face/candidates")

    assert response.status_code == 404
    assert response.json() == {"detail": "Face not found"}


def test_face_candidates_api_returns_409_when_source_embedding_is_missing(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "face-candidates-missing-embedding.db")

    engine = create_engine(
        f"sqlite:///{tmp_path / 'face-candidates-missing-embedding.db'}",
        future=True,
    )
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        connection.execute(
            insert(faces).values(
                face_id="source-face",
                photo_id="photo-1",
                person_id=None,
                embedding=None,
            )
        )

    response = client.get("/api/v1/faces/source-face/candidates")

    assert response.status_code == 409
    assert response.json() == {"detail": "Face embedding not available"}


def test_face_candidates_api_rejects_limit_out_of_bounds(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "face-candidates-invalid-limit.db")

    response = client.get("/api/v1/faces/face-1/candidates", params={"limit": 0})

    assert response.status_code == 422


def test_openapi_schema_includes_face_candidate_lookup_path(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "face-candidates-openapi.db")

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/faces/{face_id}/candidates" in schema["paths"]
    assert schema["paths"]["/api/v1/faces/{face_id}/candidates"]["get"]["responses"]["409"][
        "description"
    ] == "Face embedding not available"
