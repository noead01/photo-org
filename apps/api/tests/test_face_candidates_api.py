from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import face_labels, faces, people, photos
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
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.75")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.95")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_MODEL_VERSION", "recognition-cosine-v1")
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
    assert payload["candidates"][0]["confidence"] == pytest.approx(0.999949, abs=1e-4)
    assert payload["candidates"][1]["confidence"] == pytest.approx(0.8, abs=1e-6)
    assert payload["suggestion_policy"] == {
        "decision": "review_needed",
        "review_threshold": 0.75,
        "auto_accept_threshold": 0.95,
        "top_candidate_confidence": pytest.approx(0.999949, abs=1e-4),
    }
    assert "auto_applied_assignment" not in payload

    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "source-face")
        ).scalar_one_or_none()
        persisted_label = connection.execute(
            select(
                face_labels.c.face_id,
                face_labels.c.person_id,
                face_labels.c.label_source,
                face_labels.c.confidence,
                face_labels.c.model_version,
                face_labels.c.provenance,
            ).where(face_labels.c.face_id == "source-face")
        ).mappings().one()
    assert persisted_person_id is None
    assert persisted_label["face_id"] == "source-face"
    assert persisted_label["person_id"] == "person-1"
    assert persisted_label["label_source"] == "machine_suggested"
    assert persisted_label["confidence"] == pytest.approx(0.999949, abs=1e-4)
    assert persisted_label["model_version"] == "recognition-cosine-v1"
    assert persisted_label["provenance"] == {
        "workflow": "recognition-suggestions",
        "surface": "api",
        "action": "review_needed",
        "matched_face_id": "candidate-1-best",
        "review_threshold": 0.75,
        "auto_accept_threshold": 0.95,
        "prediction_source": "nearest-neighbor",
        "distance_metric": "cosine",
        "candidate_distance": pytest.approx(0.000051, abs=1e-4),
        "candidate_confidence": pytest.approx(0.999949, abs=1e-4),
    }


def test_face_candidates_api_returns_review_needed_state_for_medium_confidence_matches(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.75")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.95")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_MODEL_VERSION", "recognition-cosine-v1")
    client = _client(tmp_path, monkeypatch, "face-candidates-review-needed.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'face-candidates-review-needed.db'}", future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_photo(connection, photo_id="photo-2")
        _insert_person(connection, person_id="person-1", display_name="Alex")
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
                    "face_id": "candidate-1",
                    "photo_id": "photo-2",
                    "person_id": "person-1",
                    "embedding": _embedding(0.8, 0.6),
                },
            ],
        )

    response = client.get("/api/v1/faces/source-face/candidates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["face_id"] == "source-face"
    assert payload["suggestion_policy"] == {
        "decision": "review_needed",
        "review_threshold": 0.75,
        "auto_accept_threshold": 0.95,
        "top_candidate_confidence": pytest.approx(0.8, abs=1e-6),
    }
    assert payload["review_needed_suggestion"] == {
        "face_id": "source-face",
        "photo_id": "photo-1",
        "person_id": "person-1",
        "confidence": pytest.approx(0.8, abs=1e-6),
        "matched_face_id": "candidate-1",
    }
    assert "auto_applied_assignment" not in payload

    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "source-face")
        ).scalar_one_or_none()
        persisted_label = connection.execute(
            select(
                face_labels.c.face_id,
                face_labels.c.person_id,
                face_labels.c.label_source,
                face_labels.c.confidence,
                face_labels.c.model_version,
                face_labels.c.provenance,
            ).where(face_labels.c.face_id == "source-face")
        ).mappings().one()

    assert persisted_person_id is None
    assert persisted_label["face_id"] == "source-face"
    assert persisted_label["person_id"] == "person-1"
    assert persisted_label["label_source"] == "machine_suggested"
    assert persisted_label["confidence"] == pytest.approx(0.8, abs=1e-6)
    assert persisted_label["model_version"] == "recognition-cosine-v1"
    assert persisted_label["provenance"] == {
        "workflow": "recognition-suggestions",
        "surface": "api",
        "action": "review_needed",
        "matched_face_id": "candidate-1",
        "review_threshold": 0.75,
        "auto_accept_threshold": 0.95,
        "prediction_source": "nearest-neighbor",
        "distance_metric": "cosine",
        "candidate_distance": pytest.approx(0.2, abs=1e-6),
        "candidate_confidence": pytest.approx(0.8, abs=1e-6),
    }


def test_face_candidates_api_returns_no_suggestion_when_best_confidence_is_below_review_threshold(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.95")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.99")
    client = _client(tmp_path, monkeypatch, "face-candidates-threshold-policy.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'face-candidates-threshold-policy.db'}", future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_photo(connection, photo_id="photo-2")
        _insert_person(connection, person_id="person-1", display_name="Alex")
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
                    "face_id": "candidate-1",
                    "photo_id": "photo-2",
                    "person_id": "person-1",
                    "embedding": _embedding(0.8, 0.6),
                },
            ],
        )

    response = client.get("/api/v1/faces/source-face/candidates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["face_id"] == "source-face"
    assert payload["candidates"] == []
    assert payload["suggestion_policy"] == {
        "decision": "no_suggestion",
        "review_threshold": 0.95,
        "auto_accept_threshold": 0.99,
        "top_candidate_confidence": pytest.approx(0.8, abs=1e-6),
    }
    assert "auto_applied_assignment" not in payload


def test_face_candidates_api_does_not_overwrite_existing_assignment_when_policy_is_review_needed(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.75")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.95")
    client = _client(tmp_path, monkeypatch, "face-candidates-no-overwrite.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'face-candidates-no-overwrite.db'}", future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_photo(connection, photo_id="photo-2")
        _insert_person(connection, person_id="person-1", display_name="Alex")
        _insert_person(connection, person_id="person-2", display_name="Blair")
        connection.execute(
            insert(faces),
            [
                {
                    "face_id": "source-face",
                    "photo_id": "photo-1",
                    "person_id": "person-2",
                    "embedding": _embedding(1.0, 0.0),
                },
                {
                    "face_id": "candidate-1-best",
                    "photo_id": "photo-2",
                    "person_id": "person-1",
                    "embedding": _embedding(0.99, 0.01),
                },
            ],
        )

    response = client.get("/api/v1/faces/source-face/candidates", params={"limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestion_policy"]["decision"] == "review_needed"
    assert "auto_applied_assignment" not in payload
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "source-face")
        ).scalar_one()
        machine_labels = connection.execute(
            select(face_labels.c.face_label_id).where(face_labels.c.face_id == "source-face")
        ).all()
    assert persisted_person_id == "person-2"
    assert machine_labels == []


def test_face_candidates_api_returns_404_for_missing_face(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "face-candidates-missing-face.db")

    response = client.get("/api/v1/faces/missing-face/candidates")

    assert response.status_code == 404
    assert response.json() == {"detail": "Face not found"}


def test_face_candidates_api_returns_no_suggestions_when_source_embedding_is_missing(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.75")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.95")
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

    assert response.status_code == 200
    assert response.json() == {
        "face_id": "source-face",
        "candidates": [],
        "suggestion_policy": {
            "decision": "no_suggestion",
            "review_threshold": 0.75,
            "auto_accept_threshold": 0.95,
            "top_candidate_confidence": None,
        },
        "review_needed_suggestion": None,
    }


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
    assert "409" not in schema["paths"]["/api/v1/faces/{face_id}/candidates"]["get"]["responses"]
