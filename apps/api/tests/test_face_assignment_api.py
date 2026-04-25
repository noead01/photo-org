from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import face_labels, faces, people, photos


def _client(tmp_path, monkeypatch, filename: str) -> TestClient:
    database_url = f"sqlite:///{tmp_path / filename}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()
    return TestClient(app)


def _database_url(tmp_path, filename: str) -> str:
    return f"sqlite:///{tmp_path / filename}"


def _insert_photo(connection, *, photo_id: str) -> None:
    now = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    connection.execute(
        insert(photos).values(
            photo_id=photo_id,
            sha256=f"sha256-{photo_id}",
            created_ts=now,
            updated_ts=now,
        )
    )


def _insert_person(connection, *, person_id: str, display_name: str) -> None:
    now = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    connection.execute(
        insert(people).values(
            person_id=person_id,
            display_name=display_name,
            created_ts=now,
            updated_ts=now,
        )
    )


def test_face_assignment_api_assigns_unlabeled_face_to_existing_person(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_person(connection, person_id="person-1", display_name="Jane Doe")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
            )
        )

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "person-1"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "face_id": "face-1",
        "photo_id": "photo-1",
        "person_id": "person-1",
    }
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id == "person-1"


def test_face_assignment_api_does_not_create_face_label_records_in_issue_42_slice(
    tmp_path, monkeypatch
):
    database_url = _database_url(tmp_path, "face-assign-no-face-label-write.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_person(connection, person_id="person-1", display_name="Jane Doe")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
            )
        )

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "person-1"},
    )

    assert response.status_code == 201
    with engine.connect() as connection:
        face_label_count = connection.execute(select(face_labels.c.face_label_id)).all()
    assert face_label_count == []


def test_face_assignment_api_returns_404_for_missing_face(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign-missing-face.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_person(connection, person_id="person-1", display_name="Jane Doe")

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/missing-face/assignments",
        json={"person_id": "person-1"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Face not found"


def test_face_assignment_api_returns_404_for_missing_person(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign-missing-person.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
            )
        )

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "missing-person"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id is None


def test_face_assignment_api_returns_409_for_already_assigned_face(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign-already-assigned.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_person(connection, person_id="person-1", display_name="Jane Doe")
        _insert_person(connection, person_id="person-2", display_name="John Doe")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id="person-2",
            )
        )

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "person-1"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Face already assigned"
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id == "person-2"


def test_face_assignment_api_returns_422_for_blank_person_id(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign-blank-person-id.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
            )
        )

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "   "},
    )

    assert response.status_code == 422
    assert any(error["loc"][-1] == "person_id" for error in response.json()["detail"])
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id is None


def test_face_assignment_api_returns_422_for_missing_person_id(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign-missing-person-id.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
            )
        )

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={},
    )

    assert response.status_code == 422
    assert any(error["loc"][-1] == "person_id" for error in response.json()["detail"])
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id is None


def test_face_assignment_api_returns_409_when_reassigning_to_same_person(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign-same-person-conflict.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_person(connection, person_id="person-1", display_name="Jane Doe")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id="person-1",
            )
        )

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "person-1"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Face already assigned"


def test_photo_detail_api_includes_face_id_for_assignment_workflow(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign-photo-detail.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                sha256="sha-1",
                created_ts=now,
                updated_ts=now,
                path="/photos/photo-1.jpg",
                filesize=1024,
                ext="jpg",
                faces_count=1,
            )
        )
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
                bbox_x=10,
                bbox_y=20,
                bbox_w=30,
                bbox_h=40,
            )
        )

    client = TestClient(app)
    response = client.get("/api/v1/photos/photo-1")

    assert response.status_code == 200
    assert response.json()["faces"] == [
        {
            "face_id": "face-1",
            "person_id": None,
            "bbox_x": 10,
            "bbox_y": 20,
            "bbox_w": 30,
            "bbox_h": 40,
        }
    ]


def test_openapi_schema_includes_face_assignment_path_and_tag(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "face-assign-openapi.db")

    schema = client.get("/openapi.json").json()

    assert "/api/v1/faces/{face_id}/assignments" in schema["paths"]
    assert any(tag["name"] == "face-labeling" for tag in schema["tags"])
