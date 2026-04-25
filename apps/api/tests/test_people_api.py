from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, update

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import people


def _client(tmp_path, monkeypatch, filename: str) -> TestClient:
    database_url = f"sqlite:///{tmp_path / filename}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()
    return TestClient(app)


def _database_url(tmp_path, filename: str) -> str:
    return f"sqlite:///{tmp_path / filename}"


def _parse_api_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
    return parsed


def test_people_create_api_trims_display_name_and_returns_created_record(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-create.db")

    response = client.post("/api/v1/people", json={"display_name": "  Jane Doe  "})

    assert response.status_code == 201
    payload = response.json()
    assert payload["person_id"]
    assert payload["display_name"] == "Jane Doe"
    assert payload["created_ts"]
    assert payload["updated_ts"] == payload["created_ts"]


def test_people_create_api_persists_created_person_across_requests(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-create-persistence.db")

    create_response = client.post("/api/v1/people", json={"display_name": "Jane Doe"})
    person_id = create_response.json()["person_id"]

    get_response = client.get(f"/api/v1/people/{person_id}")

    assert create_response.status_code == 201
    assert get_response.status_code == 200
    assert get_response.json()["person_id"] == person_id
    assert get_response.json()["display_name"] == "Jane Doe"


def test_people_create_api_rejects_blank_display_name(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-create-blank.db")

    response = client.post("/api/v1/people", json={"display_name": "   "})

    assert response.status_code == 422
    assert any(error["loc"][-1] == "display_name" for error in response.json()["detail"])


def test_people_list_api_orders_by_display_name_then_person_id(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "people-list.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    now = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(people),
            [
                {
                    "person_id": "person-b",
                    "display_name": "Alex",
                    "created_ts": now,
                    "updated_ts": now,
                },
                {
                    "person_id": "person-c",
                    "display_name": "Bea",
                    "created_ts": now,
                    "updated_ts": now,
                },
                {
                    "person_id": "person-a",
                    "display_name": "Alex",
                    "created_ts": now,
                    "updated_ts": now,
                },
            ],
        )

    client = TestClient(app)
    response = client.get("/api/v1/people")

    assert response.status_code == 200
    payload = response.json()
    assert [item["person_id"] for item in payload] == [
        "person-a",
        "person-b",
        "person-c",
    ]
    for item in payload:
        _parse_api_timestamp(item["created_ts"])
        _parse_api_timestamp(item["updated_ts"])


def test_people_get_api_returns_existing_person(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "people-get.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    now = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(people).values(
                person_id="person-1",
                display_name="Jane Doe",
                created_ts=now,
                updated_ts=now,
            )
        )

    client = TestClient(app)
    response = client.get("/api/v1/people/person-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["person_id"] == "person-1"
    assert payload["display_name"] == "Jane Doe"
    assert _parse_api_timestamp(payload["created_ts"]) == now
    assert _parse_api_timestamp(payload["updated_ts"]) == now


def test_people_get_api_returns_404_for_missing_person(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-get-missing.db")

    response = client.get("/api/v1/people/missing-person")

    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"


def test_people_update_api_renames_person_and_refreshes_updated_timestamp(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "people-update.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    original_ts = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(people).values(
                person_id="person-1",
                display_name="Jane Doe",
                created_ts=original_ts,
                updated_ts=original_ts,
            )
        )
        connection.execute(
            update(people)
            .where(people.c.person_id == "person-1")
            .values(updated_ts=original_ts)
        )

    client = TestClient(app)
    response = client.patch(
        "/api/v1/people/person-1",
        json={"display_name": "  Jane Smith  "},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["person_id"] == "person-1"
    assert payload["display_name"] == "Jane Smith"
    created_ts = _parse_api_timestamp(payload["created_ts"])
    updated_ts = _parse_api_timestamp(payload["updated_ts"])
    assert created_ts == original_ts
    assert updated_ts > original_ts

    get_response = client.get("/api/v1/people/person-1")
    assert get_response.status_code == 200
    persisted_payload = get_response.json()
    assert persisted_payload["person_id"] == payload["person_id"]
    assert persisted_payload["display_name"] == payload["display_name"]
    assert _parse_api_timestamp(persisted_payload["created_ts"]) == created_ts
    assert _parse_api_timestamp(persisted_payload["updated_ts"]) == updated_ts


def test_people_update_api_rejects_blank_display_name(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-update-blank.db")

    response = client.patch("/api/v1/people/person-1", json={"display_name": "   "})

    assert response.status_code == 422
    assert any(error["loc"][-1] == "display_name" for error in response.json()["detail"])


def test_people_update_api_returns_404_for_missing_person(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-update-missing.db")

    response = client.patch("/api/v1/people/missing-person", json={"display_name": "Jane Doe"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"


def test_openapi_schema_includes_people_tag_and_paths(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-openapi.db")

    schema = client.get("/openapi.json").json()

    assert any(tag["name"] == "people" for tag in schema["tags"])
    assert "/api/v1/people" in schema["paths"]
    assert "/api/v1/people/{person_id}" in schema["paths"]
