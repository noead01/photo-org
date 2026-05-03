from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, delete, insert, select

from app.migrations import upgrade_database
from app.services.person_representations import refresh_person_representation
from app.storage import face_labels, faces, people, person_representations, photos


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


def test_refresh_person_representation_uses_human_confirmed_faces_only(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'person-representation.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)

    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_photo(connection, photo_id="photo-2")
        _insert_photo(connection, photo_id="photo-3")
        _insert_person(connection, person_id="person-1", display_name="Olivier")

        connection.execute(
            insert(faces),
            [
                {
                    "face_id": "face-1",
                    "photo_id": "photo-1",
                    "person_id": "person-1",
                    "embedding": [1.0, 0.0],
                },
                {
                    "face_id": "face-2",
                    "photo_id": "photo-2",
                    "person_id": "person-1",
                    "embedding": [0.0, 1.0],
                },
                {
                    "face_id": "face-3",
                    "photo_id": "photo-3",
                    "person_id": "person-1",
                    "embedding": [0.6, 0.8],
                },
            ],
        )
        connection.execute(
            insert(face_labels),
            [
                {
                    "face_label_id": "label-1",
                    "face_id": "face-1",
                    "person_id": "person-1",
                    "label_source": "human_confirmed",
                },
                {
                    "face_label_id": "label-2",
                    "face_id": "face-2",
                    "person_id": "person-1",
                    "label_source": "human_confirmed",
                },
                {
                    "face_label_id": "label-3",
                    "face_id": "face-3",
                    "person_id": "person-1",
                    "label_source": "machine_suggested",
                },
                {
                    "face_label_id": "label-4",
                    "face_id": "face-1",
                    "person_id": "person-1",
                    "label_source": "human_confirmed",
                },
            ],
        )

        refresh_person_representation(connection, person_id="person-1")
        row = connection.execute(
            select(person_representations).where(person_representations.c.person_id == "person-1")
        ).mappings().one()

    assert row["confirmed_face_count"] == 2
    assert row["centroid_embedding"] == [0.5, 0.5]
    assert row["dispersion_score"] is not None


def test_refresh_person_representation_increments_representation_version(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'person-representation-version.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)

    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_photo(connection, photo_id="photo-2")
        _insert_person(connection, person_id="person-1", display_name="Olivier")
        connection.execute(
            insert(faces),
            [
                {
                    "face_id": "face-1",
                    "photo_id": "photo-1",
                    "person_id": "person-1",
                    "embedding": [1.0, 0.0],
                },
                {
                    "face_id": "face-2",
                    "photo_id": "photo-2",
                    "person_id": "person-1",
                    "embedding": [0.0, 1.0],
                },
            ],
        )
        connection.execute(
            insert(face_labels),
            [
                {
                    "face_label_id": "label-1",
                    "face_id": "face-1",
                    "person_id": "person-1",
                    "label_source": "human_confirmed",
                },
                {
                    "face_label_id": "label-2",
                    "face_id": "face-2",
                    "person_id": "person-1",
                    "label_source": "human_confirmed",
                },
            ],
        )

        refresh_person_representation(connection, person_id="person-1")
        refresh_person_representation(connection, person_id="person-1")
        row = connection.execute(
            select(person_representations).where(person_representations.c.person_id == "person-1")
        ).mappings().one()

    assert row["representation_version"] == 2


def test_refresh_person_representation_deletes_row_when_no_human_confirmed_examples(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'person-representation-delete.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)

    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_person(connection, person_id="person-1", display_name="Olivier")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id="person-1",
                embedding=[1.0, 0.0],
            )
        )
        connection.execute(
            insert(face_labels).values(
                face_label_id="label-1",
                face_id="face-1",
                person_id="person-1",
                label_source="human_confirmed",
            )
        )
        refresh_person_representation(connection, person_id="person-1")
        connection.execute(delete(face_labels).where(face_labels.c.face_label_id == "label-1"))
        refresh_person_representation(connection, person_id="person-1")
        row = connection.execute(
            select(person_representations).where(person_representations.c.person_id == "person-1")
        ).mappings().one_or_none()

    assert row is None
