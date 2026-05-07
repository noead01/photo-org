from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from app.dependencies import FACE_VALIDATION_ROLE_HEADER, _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import face_suggestions, faces, people, photo_exif_attributes, photos


def _client(tmp_path, monkeypatch, filename: str) -> TestClient:
    database_url = f"sqlite:///{tmp_path / filename}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()
    return TestClient(app)


def _authorized_client(tmp_path, monkeypatch, filename: str) -> TestClient:
    client = _client(tmp_path, monkeypatch, filename)
    client.headers[FACE_VALIDATION_ROLE_HEADER] = "contributor"
    return client


def _insert_photo(connection, *, photo_id: str, path: str, shot_ts: datetime | None) -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    values = {
        "photo_id": photo_id,
        "sha256": f"sha256-{photo_id}",
        "path": path,
        "ext": "jpg",
        "filesize": 1024,
        "created_ts": now,
        "updated_ts": now,
        "faces_count": 0,
    }
    if shot_ts is not None:
        values["shot_ts"] = shot_ts
    connection.execute(insert(photos).values(**values))


def _insert_person(connection, *, person_id: str, display_name: str) -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    connection.execute(
        insert(people).values(
            person_id=person_id,
            display_name=display_name,
            created_ts=now,
            updated_ts=now,
        )
    )


def test_face_suggestion_review_list_returns_paginated_unassigned_faces_with_top_suggestion(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path, monkeypatch, "face-suggestion-review-list.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'face-suggestion-review-list.db'}", future=True)
    with engine.begin() as connection:
        _insert_person(connection, person_id="person-1", display_name="Alex")
        _insert_person(connection, person_id="person-2", display_name="Blair")

        _insert_photo(
            connection,
            photo_id="photo-1",
            path="/photos/1.jpg",
            shot_ts=datetime(2026, 5, 5, 11, 0, tzinfo=UTC),
        )
        _insert_photo(
            connection,
            photo_id="photo-2",
            path="/photos/2.jpg",
            shot_ts=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
        )
        _insert_photo(
            connection,
            photo_id="photo-3",
            path="/photos/3.jpg",
            shot_ts=datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
        )

        connection.execute(
            insert(faces),
            [
                {"face_id": "face-1", "photo_id": "photo-1", "person_id": None, "bbox_x": 10, "bbox_y": 20, "bbox_w": 30, "bbox_h": 40},
                {"face_id": "face-2", "photo_id": "photo-1", "person_id": None, "bbox_x": 11, "bbox_y": 21, "bbox_w": 31, "bbox_h": 41},
                {"face_id": "face-3", "photo_id": "photo-2", "person_id": None, "bbox_x": 12, "bbox_y": 22, "bbox_w": 32, "bbox_h": 42},
                {"face_id": "face-4", "photo_id": "photo-3", "person_id": "person-2", "bbox_x": 13, "bbox_y": 23, "bbox_w": 33, "bbox_h": 43},
            ],
        )
        connection.execute(
            faces.update()
            .where(faces.c.face_id == "face-1")
            .values(provenance={"bbox_space_width": 4000, "bbox_space_height": 3000})
        )
        connection.execute(
            insert(photo_exif_attributes),
            [
                {
                    "photo_id": "photo-1",
                    "exif_attribute_name": "exif_ifd.ExifImageWidth",
                    "exif_attribute_value": 5000,
                },
                {
                    "photo_id": "photo-1",
                    "exif_attribute_name": "exif_ifd.ExifImageHeight",
                    "exif_attribute_value": 4000,
                },
            ],
        )
        connection.execute(
            insert(face_suggestions),
            [
                {
                    "face_suggestion_id": "s1",
                    "face_id": "face-1",
                    "person_id": "person-1",
                    "rank": 1,
                    "confidence": 0.97,
                    "centroid_distance": 0.03,
                    "knn_distance": 0.03,
                    "representation_version": 2,
                    "scoring_version": "hybrid-v1",
                    "model_version": "recognition-v1",
                },
                {
                    "face_suggestion_id": "s1b",
                    "face_id": "face-1",
                    "person_id": "person-2",
                    "rank": 2,
                    "confidence": 0.52,
                    "centroid_distance": 0.48,
                    "knn_distance": 0.48,
                    "representation_version": 2,
                    "scoring_version": "hybrid-v1",
                    "model_version": "recognition-v1",
                },
                {
                    "face_suggestion_id": "s2",
                    "face_id": "face-2",
                    "person_id": "person-2",
                    "rank": 1,
                    "confidence": 0.81,
                    "centroid_distance": 0.19,
                    "knn_distance": 0.19,
                    "representation_version": 2,
                    "scoring_version": "hybrid-v1",
                    "model_version": "recognition-v1",
                },
                {
                    "face_suggestion_id": "s3",
                    "face_id": "face-3",
                    "person_id": "person-1",
                    "rank": 1,
                    "confidence": 0.75,
                    "centroid_distance": 0.25,
                    "knn_distance": 0.25,
                    "representation_version": 2,
                    "scoring_version": "hybrid-v1",
                    "model_version": "recognition-v1",
                },
            ],
        )

    response = client.get("/api/v1/suggestions/faces", params={"page": 1, "page_size": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == {
        "page": 1,
        "page_size": 1,
        "total_items": 2,
        "total_pages": 2,
    }
    assert len(payload["items"]) == 1
    assert payload["items"][0]["photo_id"] == "photo-1"
    assert payload["items"][0]["path"] == "/photos/1.jpg"
    assert payload["items"][0]["thumbnail"] is None
    assert [face["face_id"] for face in payload["items"][0]["faces"]] == ["face-1", "face-2"]
    assert payload["items"][0]["faces"][0]["top_suggestion"] == {
        "person_id": "person-1",
        "display_name": "Alex",
        "confidence": 0.97,
    }
    assert payload["items"][0]["faces"][0]["bbox_space_width"] == 4000
    assert payload["items"][0]["faces"][0]["bbox_space_height"] == 3000
    assert payload["items"][0]["faces"][1]["bbox_space_width"] == 5000
    assert payload["items"][0]["faces"][1]["bbox_space_height"] == 4000

    response_page_two = client.get("/api/v1/suggestions/faces", params={"page": 2, "page_size": 1})
    assert response_page_two.status_code == 200
    page_two_payload = response_page_two.json()
    assert page_two_payload["items"][0]["photo_id"] == "photo-2"
    assert [face["face_id"] for face in page_two_payload["items"][0]["faces"]] == ["face-3"]

    response_filtered = client.get(
        "/api/v1/suggestions/faces",
        params={"page": 1, "page_size": 24, "min_confidence": 0.9},
    )
    assert response_filtered.status_code == 200
    filtered_payload = response_filtered.json()
    assert filtered_payload["page"] == {
        "page": 1,
        "page_size": 24,
        "total_items": 1,
        "total_pages": 1,
    }
    assert len(filtered_payload["items"]) == 1
    assert filtered_payload["items"][0]["photo_id"] == "photo-1"
    assert [face["face_id"] for face in filtered_payload["items"][0]["faces"]] == ["face-1"]


def test_face_suggestion_review_list_omits_dismissed_faces(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "face-suggestion-review-dismissed.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'face-suggestion-review-dismissed.db'}", future=True)
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    with engine.begin() as connection:
        _insert_person(connection, person_id="person-1", display_name="Alex")
        _insert_photo(
            connection,
            photo_id="photo-1",
            path="/photos/1.jpg",
            shot_ts=datetime(2026, 5, 5, 11, 0, tzinfo=UTC),
        )
        connection.execute(
            insert(faces).values(
                face_id="face-active",
                photo_id="photo-1",
                person_id=None,
            )
        )
        connection.execute(
            insert(faces).values(
                face_id="face-dismissed",
                photo_id="photo-1",
                person_id=None,
                dismissed_ts=now,
                dismissal_provenance={
                    "workflow": "face-labeling",
                    "surface": "api",
                    "action": "dismiss_false_positive",
                },
            )
        )
        connection.execute(
            insert(face_suggestions),
            [
                {
                    "face_suggestion_id": "s1",
                    "face_id": "face-active",
                    "person_id": "person-1",
                    "rank": 1,
                    "confidence": 0.95,
                    "centroid_distance": 0.05,
                    "knn_distance": 0.05,
                    "representation_version": 2,
                    "scoring_version": "hybrid-v1",
                    "model_version": "recognition-v1",
                },
                {
                    "face_suggestion_id": "s2",
                    "face_id": "face-dismissed",
                    "person_id": "person-1",
                    "rank": 1,
                    "confidence": 0.96,
                    "centroid_distance": 0.04,
                    "knn_distance": 0.04,
                    "representation_version": 2,
                    "scoring_version": "hybrid-v1",
                    "model_version": "recognition-v1",
                },
            ],
        )

    response = client.get("/api/v1/suggestions/faces", params={"page": 1, "page_size": 24})

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"]["total_items"] == 1
    assert [face["face_id"] for face in payload["items"][0]["faces"]] == ["face-active"]


def test_face_suggestion_review_confirmation_assigns_selected_faces_to_top_suggestions(
    tmp_path,
    monkeypatch,
):
    client = _authorized_client(tmp_path, monkeypatch, "face-suggestion-review-confirm.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'face-suggestion-review-confirm.db'}", future=True)
    with engine.begin() as connection:
        _insert_person(connection, person_id="person-1", display_name="Alex")
        _insert_photo(
            connection,
            photo_id="photo-1",
            path="/photos/1.jpg",
            shot_ts=datetime(2026, 5, 5, 11, 0, tzinfo=UTC),
        )
        connection.execute(
            insert(faces),
            [
                {"face_id": "face-1", "photo_id": "photo-1", "person_id": None},
                {"face_id": "face-2", "photo_id": "photo-1", "person_id": None},
            ],
        )
        connection.execute(
            insert(face_suggestions),
            [
                {
                    "face_suggestion_id": "s1",
                    "face_id": "face-1",
                    "person_id": "person-1",
                    "rank": 1,
                    "confidence": 0.93,
                    "centroid_distance": 0.07,
                    "knn_distance": 0.07,
                    "representation_version": 2,
                    "scoring_version": "hybrid-v1",
                    "model_version": "recognition-v1",
                },
                {
                    "face_suggestion_id": "s2",
                    "face_id": "face-2",
                    "person_id": "person-1",
                    "rank": 1,
                    "confidence": 0.88,
                    "centroid_distance": 0.12,
                    "knn_distance": 0.12,
                    "representation_version": 2,
                    "scoring_version": "hybrid-v1",
                    "model_version": "recognition-v1",
                },
            ],
        )

    response = client.post(
        "/api/v1/suggestions/confirmations",
        json={"face_ids": ["face-1"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assigned"] == [
        {
            "face_id": "face-1",
            "photo_id": "photo-1",
            "person_id": "person-1",
        }
    ]
    assert payload["skipped"] == []

    with engine.connect() as connection:
        person_face_1 = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
        person_face_2 = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-2")
        ).scalar_one_or_none()

    assert person_face_1 == "person-1"
    assert person_face_2 is None


def test_face_suggestion_review_confirmation_requires_face_validation_role(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "face-suggestion-review-confirm-role.db")

    response = client.post(
        "/api/v1/suggestions/confirmations",
        json={"face_ids": ["face-1"]},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Face validation role required"}


def test_face_suggestion_review_confirmation_skips_faces_without_top_suggestions(
    tmp_path,
    monkeypatch,
):
    client = _authorized_client(tmp_path, monkeypatch, "face-suggestion-review-confirm-skips.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'face-suggestion-review-confirm-skips.db'}", future=True)
    with engine.begin() as connection:
        _insert_person(connection, person_id="person-1", display_name="Alex")
        _insert_photo(
            connection,
            photo_id="photo-1",
            path="/photos/1.jpg",
            shot_ts=datetime(2026, 5, 5, 11, 0, tzinfo=UTC),
        )
        connection.execute(
            insert(faces),
            [
                {"face_id": "face-1", "photo_id": "photo-1", "person_id": None},
                {"face_id": "face-2", "photo_id": "photo-1", "person_id": "person-1"},
            ],
        )
        connection.execute(
            insert(face_suggestions).values(
                face_suggestion_id="s1",
                face_id="face-1",
                person_id="person-1",
                rank=1,
                confidence=0.9,
                centroid_distance=0.1,
                knn_distance=0.1,
                representation_version=2,
                scoring_version="hybrid-v1",
                model_version="recognition-v1",
            )
        )

    response = client.post(
        "/api/v1/suggestions/confirmations",
        json={"face_ids": ["face-1", "face-2", "face-missing"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assigned"] == [
        {
            "face_id": "face-1",
            "photo_id": "photo-1",
            "person_id": "person-1",
        }
    ]
    assert payload["skipped"] == [
        {"face_id": "face-2", "reason": "already_assigned"},
        {"face_id": "face-missing", "reason": "face_not_found"},
    ]
