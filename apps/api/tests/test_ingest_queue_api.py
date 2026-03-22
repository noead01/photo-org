from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
    assert response.json()["processed"] == 1
