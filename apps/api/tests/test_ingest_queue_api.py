from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.dependencies as dependencies
from app.db.queue import IngestQueueStore
from app.db.session import create_session_factory
from app.dependencies import get_db
from app.main import app
from app.migrations import upgrade_database


SAMPLE_PAYLOAD = {
    "photo_id": "photo-1",
    "path": "queued/photo-1.heic",
    "sha256": "a" * 64,
    "filesize": 123,
    "ext": "heic",
    "created_ts": "2024-01-01T00:00:00+00:00",
    "modified_ts": "2024-01-02T00:00:00+00:00",
    "shot_ts": None,
    "shot_ts_source": None,
    "camera_make": None,
    "camera_model": None,
    "software": None,
    "orientation": None,
    "gps_latitude": None,
    "gps_longitude": None,
    "gps_altitude": None,
    "faces_count": 0,
}


@pytest.fixture
def database_url(tmp_path: pytest.TempPathFactory) -> str:
    return f"sqlite:///{tmp_path / 'ingest-queue-api.db'}"


@pytest.fixture
def queue_store(database_url: str, monkeypatch: pytest.MonkeyPatch) -> IngestQueueStore:
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    return IngestQueueStore(database_url)


@pytest.fixture
def client(database_url: str, queue_store: IngestQueueStore) -> Iterator[TestClient]:
    session_factory = create_session_factory(database_url)

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_process_queue_endpoint_rejects_missing_worker_role(client: TestClient):
    response = client.post("/api/v1/internal/ingest-queue/process")

    assert response.status_code == 403
    assert response.json() == {"detail": "Worker role required"}


def test_process_queue_endpoint_rejects_wrong_worker_role(client: TestClient):
    response = client.post(
        "/api/v1/internal/ingest-queue/process",
        headers={"X-Worker-Role": "wrong-role"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Worker role required"}


def test_poll_storage_sources_endpoint_rejects_missing_worker_role(client: TestClient):
    response = client.post("/api/v1/internal/storage-sources/poll")

    assert response.status_code == 403
    assert response.json() == {"detail": "Worker role required"}


def test_poll_storage_sources_endpoint_rejects_wrong_worker_role(client: TestClient):
    response = client.post(
        "/api/v1/internal/storage-sources/poll",
        headers={"X-Worker-Role": "wrong-role"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Worker role required"}


def test_process_queue_endpoint_forwards_limit_to_processor(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, int] = {}

    def fake_process_pending_ingest_queue(*, limit: int = 100):
        captured["limit"] = limit

        class Result:
            processed = 0
            failed = 0
            retryable_errors = 0

        return Result()

    monkeypatch.setattr(
        "app.routers.ingest_queue.process_pending_ingest_queue",
        fake_process_pending_ingest_queue,
    )

    response = client.post(
        "/api/v1/internal/ingest-queue/process",
        headers={"X-Worker-Role": "ingest-processor"},
        json={"limit": 7},
    )

    assert response.status_code == 200
    assert captured == {"limit": 7}
    assert response.json() == {
        "processed": 0,
        "failed": 0,
        "retryable_errors": 0,
    }


def test_poll_storage_sources_endpoint_forwards_queue_process_limit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, int] = {}

    class Result:
        scanned = 10
        enqueued = 7
        inserted = 3
        updated = 2
        queue_processed = 5
        queue_failed = 1
        queue_retryable_errors = 2
        poll_errors = ("marker mismatch",)
        error_count = 4

    def fake_trigger_storage_source_polling(*, queue_process_limit: int = 100):
        captured["queue_process_limit"] = queue_process_limit
        return Result()

    monkeypatch.setattr(
        "app.routers.ingest_queue.trigger_storage_source_polling",
        fake_trigger_storage_source_polling,
    )

    response = client.post(
        "/api/v1/internal/storage-sources/poll",
        headers={"X-Worker-Role": "ingest-processor"},
        json={"queue_process_limit": 333},
    )

    assert response.status_code == 200
    assert captured == {"queue_process_limit": 333}
    assert response.json() == {
        "scanned": 10,
        "enqueued": 7,
        "inserted": 3,
        "updated": 2,
        "processed": 5,
        "failed": 1,
        "retryable_errors": 2,
        "error_count": 4,
        "poll_errors": ["marker mismatch"],
    }


def test_get_db_reuses_cached_session_factory_for_database_url(monkeypatch: pytest.MonkeyPatch):
    created_for: list[str | None] = []

    class DummySession:
        def close(self) -> None:
            pass

    class DummySessionFactory:
        def __call__(self) -> DummySession:
            return DummySession()

    def fake_create_session_factory(database_url: str | None):
        created_for.append(database_url)
        return DummySessionFactory()

    dependencies._get_session_factory.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///cached.db")
    monkeypatch.setattr(dependencies, "create_session_factory", fake_create_session_factory)

    first = dependencies.get_db()
    second = dependencies.get_db()
    first_session = next(first)
    second_session = next(second)

    assert isinstance(first_session, DummySession)
    assert isinstance(second_session, DummySession)
    assert created_for == ["sqlite:///cached.db"]

    first.close()
    second.close()


def test_process_queue_endpoint_processes_pending_rows_for_worker_role(
    client: TestClient,
    queue_store: IngestQueueStore,
):
    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-1",
    )

    response = client.post(
        "/api/v1/internal/ingest-queue/process",
        headers={"X-Worker-Role": "ingest-processor"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "processed": 1,
        "failed": 0,
        "retryable_errors": 0,
    }


def test_search_endpoint_is_not_exposed_by_runtime_app(client: TestClient):
    response = client.post("/api/v1/search", json={})

    assert response.status_code == 404
