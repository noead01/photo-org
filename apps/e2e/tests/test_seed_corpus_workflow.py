from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.dev.seed_corpus import load_seed_corpus_into_database, validate_seed_corpus
from app.main import app
from app.migrations import upgrade_database
from app.db.session import create_db_engine
from app.services.ingest_queue_processor import process_pending_ingest_queue
from app.storage import faces, photos


def _load_seed_corpus(seed_corpus_database_url):
    report = validate_seed_corpus()
    assert report.errors == []

    upgrade_database(seed_corpus_database_url)
    engine = create_db_engine(seed_corpus_database_url)
    with engine.connect() as connection:
        initial_photo_count = connection.execute(
            select(func.count()).select_from(photos)
        ).scalar_one()
        initial_detected_photo_count = connection.execute(
            select(func.count())
            .select_from(photos)
            .where(photos.c.faces_detected_ts.is_not(None))
        ).scalar_one()

    load_result = load_seed_corpus_into_database(database_url=seed_corpus_database_url)

    assert load_result["processed"] == 0

    processed = 0
    while True:
        batch = process_pending_ingest_queue(seed_corpus_database_url, limit=report.asset_count)
        processed += batch.processed
        if batch.processed == 0 and batch.retryable_errors == 0:
            break

    return report, engine, initial_photo_count, initial_detected_photo_count, processed


def test_seed_corpus_can_be_ingested_and_persisted_end_to_end(seed_corpus_database_url):
    report, engine, initial_photo_count, initial_detected_photo_count, processed = _load_seed_corpus(
        seed_corpus_database_url
    )

    if initial_photo_count == 0:
        assert processed == report.asset_count
    else:
        assert initial_photo_count == report.asset_count
        assert processed == 0

    with engine.connect() as connection:
        photo_count = connection.execute(select(func.count()).select_from(photos)).scalar_one()
        detected_photo_count = connection.execute(
            select(func.count())
            .select_from(photos)
            .where(photos.c.faces_detected_ts.is_not(None))
        ).scalar_one()

    assert photo_count == report.asset_count
    if initial_photo_count == 0:
        assert detected_photo_count > 0
    else:
        assert detected_photo_count == initial_detected_photo_count

    client = TestClient(app)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_seed_corpus_read_endpoints_reflect_ingested_catalog(seed_corpus_database_url):
    report, engine, _, _, _ = _load_seed_corpus(seed_corpus_database_url)

    with engine.connect() as connection:
        expected_listing_count = connection.execute(
            select(func.count())
            .select_from(photos)
            .where(photos.c.deleted_ts.is_(None))
        ).scalar_one()
        photo_with_face_regions = connection.execute(
            select(photos.c.photo_id)
            .select_from(photos.join(faces, photos.c.photo_id == faces.c.photo_id))
            .where(photos.c.deleted_ts.is_(None))
            .where(photos.c.faces_detected_ts.is_not(None))
            .order_by(photos.c.shot_ts.desc(), photos.c.photo_id.desc())
            .limit(1)
        ).scalar_one()

    assert expected_listing_count == report.asset_count

    client = TestClient(app)

    listing_response = client.get("/api/v1/photos")
    assert listing_response.status_code == 200
    listing_payload = listing_response.json()
    assert len(listing_payload) == report.asset_count
    assert len(listing_payload) == expected_listing_count
    shot_timestamps = [row["shot_ts"] for row in listing_payload]
    non_null_shot_timestamps = [value for value in shot_timestamps if value is not None]
    assert non_null_shot_timestamps == sorted(non_null_shot_timestamps, reverse=True)
    if None in shot_timestamps:
        first_null_index = shot_timestamps.index(None)
        assert all(value is None for value in shot_timestamps[first_null_index:])

    detail_response = client.get(f"/api/v1/photos/{photo_with_face_regions}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["photo_id"] == photo_with_face_regions
    assert detail_payload["metadata"]["sha256"]
    assert detail_payload["metadata"]["faces_count"] >= 1
    assert detail_payload["faces"]
    assert all(face["bbox_x"] is not None for face in detail_payload["faces"])
    assert all(face["bbox_y"] is not None for face in detail_payload["faces"])
    assert all(face["bbox_w"] is not None for face in detail_payload["faces"])
    assert all(face["bbox_h"] is not None for face in detail_payload["faces"])
