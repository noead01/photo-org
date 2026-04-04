import yaml
from sqlalchemy import func, select

from app.db.session import create_db_engine
from app.storage import faces, photos


def test_deployment_photo_listing_matches_seed_corpus(
    seed_corpus_database_url,
    deployment_api_client,
):
    engine = create_db_engine(seed_corpus_database_url)
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

    listing_response = deployment_api_client.get("/api/v1/photos")

    assert listing_response.status_code == 200
    listing_payload = listing_response.json()
    assert len(listing_payload) == expected_listing_count
    assert any(row["photo_id"] == photo_with_face_regions for row in listing_payload)

    shot_timestamps = [row["shot_ts"] for row in listing_payload]
    non_null_shot_timestamps = [value for value in shot_timestamps if value is not None]
    assert non_null_shot_timestamps == sorted(non_null_shot_timestamps, reverse=True)
    if None in shot_timestamps:
        first_null_index = shot_timestamps.index(None)
        assert all(value is None for value in shot_timestamps[first_null_index:])


def test_deployment_photo_detail_matches_seed_corpus(
    seed_corpus_database_url,
    deployment_api_client,
):
    engine = create_db_engine(seed_corpus_database_url)
    with engine.connect() as connection:
        photo_with_face_regions = connection.execute(
            select(photos.c.photo_id)
            .select_from(photos.join(faces, photos.c.photo_id == faces.c.photo_id))
            .where(photos.c.deleted_ts.is_(None))
            .where(photos.c.faces_detected_ts.is_not(None))
            .order_by(photos.c.shot_ts.desc(), photos.c.photo_id.desc())
            .limit(1)
        ).scalar_one()

    detail_response = deployment_api_client.get(f"/api/v1/photos/{photo_with_face_regions}")

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


def test_deployment_openapi_json_and_yaml_match(deployment_api_client):
    json_response = deployment_api_client.get("/openapi.json")
    yaml_response = deployment_api_client.get("/openapi.yaml")

    assert json_response.status_code == 200
    assert yaml_response.status_code == 200
    assert "application/json" in json_response.headers["content-type"]
    assert "application/yaml" in yaml_response.headers["content-type"]

    json_payload = json_response.json()
    yaml_payload = yaml.safe_load(yaml_response.text)

    assert json_payload == yaml_payload
    assert json_payload["info"]["title"] == "Photo Organizer API"
    assert "/api/v1/photos" in json_payload["paths"]
    assert "/api/v1/photos/{photo_id}" in json_payload["paths"]


def test_deployment_docs_surface_is_served(deployment_api_client):
    docs_response = deployment_api_client.get("/docs")

    assert docs_response.status_code == 200
    assert "text/html" in docs_response.headers["content-type"]
    assert "Swagger UI" in docs_response.text
    assert "/openapi.json" in docs_response.text
