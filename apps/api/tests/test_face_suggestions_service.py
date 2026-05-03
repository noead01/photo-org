from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, insert, select

from app.migrations import upgrade_database
from app.services.face_suggestions import refresh_face_suggestions_for_face
from app.storage import (
    face_labels,
    face_suggestions,
    faces,
    people,
    person_representations,
    photos,
)


def _insert_photo(connection, *, photo_id: str) -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
    connection.execute(
        insert(photos).values(
            photo_id=photo_id,
            sha256=f"sha256-{photo_id}",
            created_ts=now,
            updated_ts=now,
        )
    )


def _insert_person(connection, *, person_id: str, display_name: str) -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
    connection.execute(
        insert(people).values(
            person_id=person_id,
            display_name=display_name,
            created_ts=now,
            updated_ts=now,
        )
    )


def test_refresh_face_suggestions_persists_ranked_candidates(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'face-suggestions-ranked.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)

    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-source")
        _insert_photo(connection, photo_id="photo-a")
        _insert_photo(connection, photo_id="photo-b")
        _insert_photo(connection, photo_id="photo-c")
        _insert_person(connection, person_id="person-a", display_name="Alex")
        _insert_person(connection, person_id="person-b", display_name="Blair")
        _insert_person(connection, person_id="person-c", display_name="Casey")

        connection.execute(
            insert(faces),
            [
                {
                    "face_id": "face-source",
                    "photo_id": "photo-source",
                    "person_id": None,
                    "embedding": [1.0, 0.0],
                },
                {
                    "face_id": "face-a",
                    "photo_id": "photo-a",
                    "person_id": "person-a",
                    "embedding": [0.99, 0.01],
                },
                {
                    "face_id": "face-b",
                    "photo_id": "photo-b",
                    "person_id": "person-b",
                    "embedding": [0.75, 0.25],
                },
                {
                    "face_id": "face-c",
                    "photo_id": "photo-c",
                    "person_id": "person-c",
                    "embedding": [0.0, 1.0],
                },
            ],
        )

        connection.execute(
            insert(person_representations),
            [
                {
                    "person_id": "person-a",
                    "centroid_embedding": [0.98, 0.02],
                    "confirmed_face_count": 4,
                    "dispersion_score": 0.01,
                    "representation_version": 7,
                    "model_version": "nearest-neighbor-cosine-v1",
                },
                {
                    "person_id": "person-b",
                    "centroid_embedding": [0.8, 0.2],
                    "confirmed_face_count": 3,
                    "dispersion_score": 0.03,
                    "representation_version": 7,
                    "model_version": "nearest-neighbor-cosine-v1",
                },
                {
                    "person_id": "person-c",
                    "centroid_embedding": [0.2, 0.8],
                    "confirmed_face_count": 5,
                    "dispersion_score": 0.04,
                    "representation_version": 7,
                    "model_version": "nearest-neighbor-cosine-v1",
                },
            ],
        )

        connection.execute(
            insert(face_labels),
            [
                {
                    "face_label_id": "label-a",
                    "face_id": "face-a",
                    "person_id": "person-a",
                    "label_source": "human_confirmed",
                },
                {
                    "face_label_id": "label-b",
                    "face_id": "face-b",
                    "person_id": "person-b",
                    "label_source": "human_confirmed",
                },
                {
                    "face_label_id": "label-c",
                    "face_id": "face-c",
                    "person_id": "person-c",
                    "label_source": "human_confirmed",
                },
            ],
        )

        refresh_face_suggestions_for_face(connection, face_id="face-source", limit=3)
        rows = connection.execute(
            select(face_suggestions)
            .where(face_suggestions.c.face_id == "face-source")
            .order_by(face_suggestions.c.rank.asc())
        ).mappings().all()

    assert [row["person_id"] for row in rows] == ["person-a", "person-b", "person-c"]
    assert [row["rank"] for row in rows] == [1, 2, 3]
    assert rows[0]["confidence"] >= rows[1]["confidence"] >= rows[2]["confidence"]


def test_refresh_face_suggestions_replaces_stale_snapshot_rows(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'face-suggestions-replace.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)

    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-source")
        _insert_photo(connection, photo_id="photo-a")
        _insert_person(connection, person_id="person-a", display_name="Alex")
        connection.execute(
            insert(faces),
            [
                {
                    "face_id": "face-source",
                    "photo_id": "photo-source",
                    "person_id": None,
                    "embedding": [1.0, 0.0],
                },
                {
                    "face_id": "face-a",
                    "photo_id": "photo-a",
                    "person_id": "person-a",
                    "embedding": [0.99, 0.01],
                },
            ],
        )
        connection.execute(
            insert(person_representations).values(
                person_id="person-a",
                centroid_embedding=[0.98, 0.02],
                confirmed_face_count=3,
                dispersion_score=0.01,
                representation_version=7,
                model_version="nearest-neighbor-cosine-v1",
            )
        )
        connection.execute(
            insert(face_labels).values(
                face_label_id="label-a",
                face_id="face-a",
                person_id="person-a",
                label_source="human_confirmed",
            )
        )
        connection.execute(
            insert(face_suggestions).values(
                face_suggestion_id="stale-row",
                face_id="face-source",
                person_id="person-a",
                rank=1,
                confidence=0.1,
                centroid_distance=0.9,
                knn_distance=0.9,
                representation_version=1,
                scoring_version="hybrid-v0",
                model_version="old",
            )
        )

        refresh_face_suggestions_for_face(connection, face_id="face-source", limit=1)
        rows = connection.execute(
            select(face_suggestions).where(face_suggestions.c.face_id == "face-source")
        ).mappings().all()

    assert len(rows) == 1
    assert rows[0]["face_suggestion_id"] != "stale-row"
    assert rows[0]["scoring_version"] == "hybrid-v1"
