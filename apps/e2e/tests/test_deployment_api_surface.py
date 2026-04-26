from uuid import uuid4

import pytest
import yaml
from sqlalchemy import func, insert, select

from app.dependencies import FACE_VALIDATION_ROLE_HEADER
from app.db.session import create_db_engine
from app.storage import face_labels, faces, photos
from photoorg_db_schema import EMBEDDING_DIMENSION


def _embedding(first: float, second: float) -> list[float]:
    values = [0.0] * EMBEDDING_DIMENSION
    values[0] = first
    values[1] = second
    return values


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
    assert "/api/v1/people" in json_payload["paths"]
    assert "/api/v1/people/{person_id}" in json_payload["paths"]
    assert "/api/v1/faces/{face_id}/assignments" in json_payload["paths"]
    assert "/api/v1/faces/{face_id}/corrections" in json_payload["paths"]


def test_deployment_people_crud_surface(deployment_api_client):
    name_token = uuid4().hex[:8]
    create_response = deployment_api_client.post(
        "/api/v1/people",
        json={"display_name": f"  E2E Person {name_token}  "},
    )

    assert create_response.status_code == 201
    created_payload = create_response.json()
    person_id = created_payload["person_id"]
    assert created_payload["display_name"] == f"E2E Person {name_token}"
    assert created_payload["created_ts"]
    assert created_payload["updated_ts"]

    get_response = deployment_api_client.get(f"/api/v1/people/{person_id}")
    assert get_response.status_code == 200
    assert get_response.json()["person_id"] == person_id

    renamed_display_name = f"Renamed E2E Person {name_token}"
    update_response = deployment_api_client.patch(
        f"/api/v1/people/{person_id}",
        json={"display_name": f"  {renamed_display_name}  "},
    )
    assert update_response.status_code == 200
    assert update_response.json()["display_name"] == renamed_display_name

    list_response = deployment_api_client.get("/api/v1/people")
    assert list_response.status_code == 200
    assert any(
        person["person_id"] == person_id and person["display_name"] == renamed_display_name
        for person in list_response.json()
    )

    delete_response = deployment_api_client.delete(f"/api/v1/people/{person_id}")
    assert delete_response.status_code == 204

    missing_response = deployment_api_client.get(f"/api/v1/people/{person_id}")
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Person not found"


def test_deployment_face_labeling_assignment_and_correction_surface(
    seed_corpus_database_url,
    deployment_api_client,
):
    engine = create_db_engine(seed_corpus_database_url)
    with engine.begin() as connection:
        photo_id = connection.execute(
            select(photos.c.photo_id)
            .where(photos.c.deleted_ts.is_(None))
            .order_by(photos.c.photo_id)
            .limit(1)
        ).scalar_one()
        face_id = str(uuid4())
        connection.execute(
            insert(faces).values(
                face_id=face_id,
                photo_id=photo_id,
                person_id=None,
            )
        )

    person_one_response = deployment_api_client.post(
        "/api/v1/people",
        json={"display_name": f"E2E Assignee One {uuid4().hex[:8]}"},
    )
    person_two_response = deployment_api_client.post(
        "/api/v1/people",
        json={"display_name": f"E2E Assignee Two {uuid4().hex[:8]}"},
    )
    assert person_one_response.status_code == 201
    assert person_two_response.status_code == 201
    person_one_id = person_one_response.json()["person_id"]
    person_two_id = person_two_response.json()["person_id"]

    unauthorized_response = deployment_api_client.post(
        f"/api/v1/faces/{face_id}/assignments",
        json={"person_id": person_one_id},
    )
    assert unauthorized_response.status_code == 403
    assert unauthorized_response.json()["detail"] == "Face validation role required"

    assignment_response = deployment_api_client.post(
        f"/api/v1/faces/{face_id}/assignments",
        headers={FACE_VALIDATION_ROLE_HEADER: "contributor"},
        json={"person_id": person_one_id},
    )
    assert assignment_response.status_code == 201
    assert assignment_response.json() == {
        "face_id": face_id,
        "photo_id": photo_id,
        "person_id": person_one_id,
    }

    correction_response = deployment_api_client.post(
        f"/api/v1/faces/{face_id}/corrections",
        headers={FACE_VALIDATION_ROLE_HEADER: "contributor"},
        json={"person_id": person_two_id},
    )
    assert correction_response.status_code == 200
    assert correction_response.json() == {
        "face_id": face_id,
        "photo_id": photo_id,
        "previous_person_id": person_one_id,
        "person_id": person_two_id,
    }


def test_deployment_face_candidate_lookup_persists_prediction_metadata(
    seed_corpus_database_url,
    deployment_api_client,
):
    person_response = deployment_api_client.post(
        "/api/v1/people",
        json={"display_name": f"E2E Candidate {uuid4().hex[:8]}"},
    )
    assert person_response.status_code == 201
    person_id = person_response.json()["person_id"]

    engine = create_db_engine(seed_corpus_database_url)
    with engine.begin() as connection:
        photo_id = connection.execute(
            select(photos.c.photo_id)
            .where(photos.c.deleted_ts.is_(None))
            .order_by(photos.c.photo_id)
            .limit(1)
        ).scalar_one()
        source_face_id = str(uuid4())
        candidate_face_id = str(uuid4())
        connection.execute(
            insert(faces),
            [
                {
                    "face_id": source_face_id,
                    "photo_id": photo_id,
                    "person_id": None,
                    "embedding": _embedding(1.0, 0.0),
                },
                {
                    "face_id": candidate_face_id,
                    "photo_id": photo_id,
                    "person_id": person_id,
                    "embedding": _embedding(0.99, 0.01),
                },
            ],
        )

    response = deployment_api_client.get(f"/api/v1/faces/{source_face_id}/candidates")
    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestion_policy"]["decision"] == "auto_apply"
    top_candidate = payload["candidates"][0]
    thresholds = payload["suggestion_policy"]

    with engine.connect() as connection:
        persisted_face = connection.execute(
            select(faces.c.person_id).where(faces.c.face_id == source_face_id)
        ).scalar_one()
        persisted_label = connection.execute(
            select(
                face_labels.c.face_id,
                face_labels.c.person_id,
                face_labels.c.label_source,
                face_labels.c.model_version,
                face_labels.c.provenance,
            ).where(face_labels.c.face_id == source_face_id)
        ).mappings().one()

    assert persisted_face == person_id
    assert persisted_label["face_id"] == source_face_id
    assert persisted_label["person_id"] == person_id
    assert persisted_label["label_source"] == "machine_applied"
    assert persisted_label["model_version"]
    assert persisted_label["provenance"] == {
        "workflow": "recognition-suggestions",
        "surface": "api",
        "action": "auto_apply",
        "matched_face_id": candidate_face_id,
        "review_threshold": pytest.approx(thresholds["review_threshold"], abs=1e-6),
        "auto_accept_threshold": pytest.approx(thresholds["auto_accept_threshold"], abs=1e-6),
        "prediction_source": "nearest-neighbor",
        "distance_metric": "cosine",
        "candidate_distance": pytest.approx(top_candidate["distance"], abs=1e-6),
        "candidate_confidence": pytest.approx(top_candidate["confidence"], abs=1e-6),
    }


def test_deployment_docs_surface_is_served(deployment_api_client):
    docs_response = deployment_api_client.get("/docs")

    assert docs_response.status_code == 200
    assert "text/html" in docs_response.headers["content-type"]
    assert "Swagger UI" in docs_response.text
    assert "/openapi.json" in docs_response.text
