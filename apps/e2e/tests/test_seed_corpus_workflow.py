from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.dev.seed_corpus import load_seed_corpus_into_database, validate_seed_corpus
from app.main import app
from app.migrations import upgrade_database
from app.db.session import create_db_engine
from app.services.ingest_queue_processor import process_pending_ingest_queue
from app.storage import photos


def test_seed_corpus_can_be_ingested_and_persisted_end_to_end(seed_corpus_database_url):
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

    engine = create_db_engine(seed_corpus_database_url)
    with engine.connect() as connection:
        photo_count = connection.execute(select(func.count()).select_from(photos)).scalar_one()

    assert photo_count == report.asset_count

    client = TestClient(app)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
