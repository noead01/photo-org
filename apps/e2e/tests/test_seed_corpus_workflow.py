from fastapi.testclient import TestClient

from app.dev.seed_corpus import load_seed_corpus_into_database, validate_seed_corpus
from app.main import app
from app.migrations import upgrade_database
from app.services.ingest_queue_processor import process_pending_ingest_queue


def test_seed_corpus_can_be_ingested_and_queried_end_to_end(seed_corpus_database_url):
    report = validate_seed_corpus()
    assert report.errors == []

    upgrade_database(seed_corpus_database_url)
    load_result = load_seed_corpus_into_database(database_url=seed_corpus_database_url)

    assert load_result["processed"] == 0

    processed = 0
    while True:
        batch = process_pending_ingest_queue(seed_corpus_database_url, limit=report.asset_count)
        processed += batch.processed
        if batch.processed == 0 and batch.retryable_errors == 0:
            break

    assert processed == report.asset_count

    client = TestClient(app)
    response = client.post(
        "/api/v1/search",
        json={
            "filters": {"camera_make": ["Canon"]},
            "sort": {"by": "shot_ts", "dir": "desc"},
            "page": {"limit": 10},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["hits"]["total"] >= 1
    assert any(item["camera_make"] == "Canon" for item in payload["hits"]["items"])
