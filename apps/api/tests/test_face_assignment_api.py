from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.dml import Update

from app.dependencies import FACE_VALIDATION_ROLE_HEADER, _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.routers import face_assignments as face_assignments_router
from app.services import face_assignment as face_assignment_service
from app.storage import face_labels, faces, people, photos


def _client(tmp_path, monkeypatch, filename: str) -> TestClient:
    database_url = f"sqlite:///{tmp_path / filename}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()
    return TestClient(app)


def _database_url(tmp_path, filename: str) -> str:
    return f"sqlite:///{tmp_path / filename}"


def _authorized_client() -> TestClient:
    client = TestClient(app)
    client.headers[FACE_VALIDATION_ROLE_HEADER] = "contributor"
    return client


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


class _FacesUpdateForeignKeyViolationConnection:
    def __init__(self, connection, *, person_id: str) -> None:
        self._connection = connection
        self._person_id = person_id
        self._did_inject = False

    def execute(self, statement, *args, **kwargs):
        if (
            not self._did_inject
            and isinstance(statement, Update)
            and statement.table.name == faces.name
        ):
            self._did_inject = True
            self._connection.execute(
                delete(people).where(people.c.person_id == self._person_id)
            )
            raise IntegrityError(
                str(statement),
                {},
                Exception("FOREIGN KEY constraint failed"),
            )
        return self._connection.execute(statement, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._connection, name)


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

    client = _authorized_client()
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


def test_face_assignment_api_rejects_missing_face_validation_role(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign-missing-role.db")
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

    assert response.status_code == 403
    assert response.json() == {"detail": "Face validation role required"}
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id is None


def test_face_assignment_api_rejects_unrecognized_face_validation_role(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign-wrong-role.db")
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
        headers={FACE_VALIDATION_ROLE_HEADER: "viewer"},
        json={"person_id": "person-1"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Face validation role required"}


def test_face_assignment_api_persists_human_confirmed_face_label_provenance(
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

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "person-1"},
    )

    assert response.status_code == 201
    with engine.connect() as connection:
        face_label_rows = connection.execute(
            select(
                face_labels.c.face_id,
                face_labels.c.person_id,
                face_labels.c.label_source,
                face_labels.c.confidence,
                face_labels.c.model_version,
                face_labels.c.provenance,
            )
        ).mappings().all()
    assert len(face_label_rows) == 1
    assert face_label_rows[0]["face_id"] == "face-1"
    assert face_label_rows[0]["person_id"] == "person-1"
    assert face_label_rows[0]["label_source"] == "human_confirmed"
    assert face_label_rows[0]["confidence"] is None
    assert face_label_rows[0]["model_version"] is None
    assert face_label_rows[0]["provenance"] == {
        "workflow": "face-labeling",
        "surface": "api",
        "action": "assignment",
    }


def test_face_assignment_api_returns_404_for_missing_face(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-assign-missing-face.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_person(connection, person_id="person-1", display_name="Jane Doe")

    client = _authorized_client()
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

    client = _authorized_client()
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


def test_face_assignment_api_returns_404_when_assignment_loses_delete_race(
    tmp_path, monkeypatch
):
    database_url = _database_url(tmp_path, "face-assign-delete-race.db")
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

    def _assign_face_with_integrity_violation(connection, *, face_id: str, person_id: str):
        wrapped_connection = _FacesUpdateForeignKeyViolationConnection(
            connection,
            person_id=person_id,
        )
        return face_assignment_service.assign_face_to_person(
            wrapped_connection,
            face_id=face_id,
            person_id=person_id,
        )

    monkeypatch.setattr(
        face_assignments_router,
        "assign_face_to_person",
        _assign_face_with_integrity_violation,
    )

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "person-1"},
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

    client = _authorized_client()
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

    client = _authorized_client()
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

    client = _authorized_client()
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

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "person-1"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Face already assigned"


def test_face_correction_api_reassigns_assigned_face_to_different_person(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-correct-reassign.db")
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
                person_id="person-1",
            )
        )

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/corrections",
        json={"person_id": "person-2"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "face_id": "face-1",
        "photo_id": "photo-1",
        "previous_person_id": "person-1",
        "person_id": "person-2",
    }
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id == "person-2"


def test_face_correction_api_rejects_missing_face_validation_role(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-correct-missing-role.db")
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
                person_id="person-1",
            )
        )

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/face-1/corrections",
        json={"person_id": "person-2"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Face validation role required"}
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id == "person-1"


def test_face_correction_api_persists_human_confirmed_face_label_provenance(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-correct-no-face-label-write.db")
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
                person_id="person-1",
            )
        )

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/corrections",
        json={"person_id": "person-2"},
    )

    assert response.status_code == 200
    with engine.connect() as connection:
        face_label_rows = connection.execute(
            select(
                face_labels.c.face_id,
                face_labels.c.person_id,
                face_labels.c.label_source,
                face_labels.c.confidence,
                face_labels.c.model_version,
                face_labels.c.provenance,
            )
        ).mappings().all()
    assert len(face_label_rows) == 1
    assert face_label_rows[0]["face_id"] == "face-1"
    assert face_label_rows[0]["person_id"] == "person-2"
    assert face_label_rows[0]["label_source"] == "human_confirmed"
    assert face_label_rows[0]["confidence"] is None
    assert face_label_rows[0]["model_version"] is None
    assert face_label_rows[0]["provenance"] == {
        "workflow": "face-labeling",
        "surface": "api",
        "action": "correction",
        "previous_person_id": "person-1",
    }


def test_face_correction_api_returns_404_for_missing_face(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-correct-missing-face.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_person(connection, person_id="person-1", display_name="Jane Doe")

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/missing-face/corrections",
        json={"person_id": "person-1"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Face not found"


def test_face_correction_api_returns_404_for_missing_person(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-correct-missing-person.db")
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

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/corrections",
        json={"person_id": "missing-person"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id == "person-1"


def test_face_correction_api_returns_404_when_correction_loses_delete_race(
    tmp_path, monkeypatch
):
    database_url = _database_url(tmp_path, "face-correct-delete-race.db")
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
                person_id="person-1",
            )
        )

    def _reassign_face_with_integrity_violation(connection, *, face_id: str, person_id: str):
        wrapped_connection = _FacesUpdateForeignKeyViolationConnection(
            connection,
            person_id=person_id,
        )
        return face_assignment_service.reassign_face_to_person(
            wrapped_connection,
            face_id=face_id,
            person_id=person_id,
        )

    monkeypatch.setattr(
        face_assignments_router,
        "reassign_face_to_person",
        _reassign_face_with_integrity_violation,
    )

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/corrections",
        json={"person_id": "person-2"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id == "person-1"


def test_face_correction_api_returns_409_when_face_is_unassigned(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-correct-unassigned.db")
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

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/corrections",
        json={"person_id": "person-1"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Face is not assigned"
    with engine.connect() as connection:
        persisted_person_id = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == "face-1")
        ).scalar_one_or_none()
    assert persisted_person_id is None


def test_face_correction_api_returns_409_when_reassigning_to_same_person(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-correct-same-person-conflict.db")
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

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/corrections",
        json={"person_id": "person-1"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Face already assigned to person"


def test_face_correction_api_returns_422_for_blank_person_id(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-correct-blank-person-id.db")
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

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/corrections",
        json={"person_id": "   "},
    )

    assert response.status_code == 422
    assert any(error["loc"][-1] == "person_id" for error in response.json()["detail"])


def test_face_correction_api_returns_422_for_missing_person_id(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-correct-missing-person-id.db")
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

    client = _authorized_client()
    response = client.post(
        "/api/v1/faces/face-1/corrections",
        json={},
    )

    assert response.status_code == 422
    assert any(error["loc"][-1] == "person_id" for error in response.json()["detail"])


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

    client = _authorized_client()
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
    assert "/api/v1/faces/{face_id}/corrections" in schema["paths"]
    assert schema["paths"]["/api/v1/faces/{face_id}/assignments"]["post"]["responses"]["403"][
        "description"
    ] == "Face validation role required"
    assert schema["paths"]["/api/v1/faces/{face_id}/corrections"]["post"]["responses"]["403"][
        "description"
    ] == "Face validation role required"
    assignment_parameters = schema["paths"]["/api/v1/faces/{face_id}/assignments"]["post"]["parameters"]
    correction_parameters = schema["paths"]["/api/v1/faces/{face_id}/corrections"]["post"]["parameters"]
    assert any(
        parameter["in"] == "header" and parameter["name"] == FACE_VALIDATION_ROLE_HEADER
        for parameter in assignment_parameters
    )
    assert any(
        parameter["in"] == "header" and parameter["name"] == FACE_VALIDATION_ROLE_HEADER
        for parameter in correction_parameters
    )
    assert any(tag["name"] == "face-labeling" for tag in schema["tags"])
