import yaml
from fastapi.testclient import TestClient

from app.main import app
from app.openapi_docs import OPENAPI_YAML_MEDIA_TYPE


class TestHealthEndpoint:
    def test_given_health_endpoint_when_making_get_request_then_returns_200_with_ok_status(self):
        """
        Given: The health check endpoint (/healthz)
        When: Making a GET request
        Then: Returns 200 status code with {"status": "ok"} response
        """
        # Given
        client = TestClient(app)
        
        # When
        response = client.get("/healthz")
        
        # Then
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_given_health_endpoint_when_making_get_request_then_returns_json_content_type(self):
        """
        Given: The health check endpoint (/healthz)
        When: Making a GET request
        Then: Returns response with JSON content type and status field
        """
        # Given
        client = TestClient(app)
        
        # When
        response = client.get("/healthz")
        
        # Then
        assert response.headers["content-type"] == "application/json"
        assert "status" in response.json()
        assert response.json()["status"] == "ok"

    def test_given_openapi_yaml_when_fetching_then_returns_yaml_with_expected_media_type(self):
        client = TestClient(app)

        response = client.get("/openapi.yaml")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith(OPENAPI_YAML_MEDIA_TYPE)
        assert yaml.safe_load(response.text) == client.get("/openapi.json").json()

    def test_given_openapi_schema_when_fetching_then_includes_health_route_and_excludes_yaml_route(self):
        client = TestClient(app)

        response = client.get("/openapi.json")

        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/healthz" in paths
        assert "/openapi.yaml" not in paths

    def test_given_openapi_schema_when_fetching_then_exposes_documented_metadata(self):
        client = TestClient(app)

        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        assert schema["info"]["title"] == "Photo Organizer API"
        assert schema["info"]["version"] == "0.1.0"
        assert "authored in the FastAPI routes and Pydantic models" in schema["info"]["description"]
        assert schema["paths"]["/api/v1/photos"]["get"]["summary"] == "List photos"
        assert schema["paths"]["/api/v1/storage-sources"]["post"]["responses"]["400"]["description"] == (
            "Storage source registration failed"
        )
        assert schema["paths"]["/api/v1/storage-sources/{storage_source_id}/watched-folders"]["post"][
            "responses"
        ]["400"]["description"] == "Watched folder validation failed"
        assert "/api/v1/operations/activity" in schema["paths"]
        assert "/api/v1/operations/activity/history" in schema["paths"]
        assert any(tag["name"] == "operations" for tag in schema["tags"])
        watched_folder_mutation_responses = schema["paths"][
            "/api/v1/storage-sources/{storage_source_id}/watched-folders/{watched_folder_id}"
        ]
        assert watched_folder_mutation_responses["patch"]["responses"]["404"]["description"] == (
            "Watched folder not found"
        )
        assert watched_folder_mutation_responses["delete"]["responses"]["404"]["description"] == (
            "Watched folder not found"
        )
        assert schema["paths"]["/api/v1/internal/ingest-queue/process"]["post"]["responses"]["403"][
            "description"
        ] == "Worker role required"
        assert (
            schema["paths"]["/api/v1/operations/activity"]["get"]["summary"]
            == "Get live operational activity"
        )
        assert (
            schema["paths"]["/api/v1/operations/activity/history"]["get"]["summary"]
            == "Get operational activity history"
        )
        assert (
            schema["components"]["schemas"]["RegisterStorageSourceRequest"]["properties"]["root_path"][
                "description"
            ]
            == "Absolute path to the storage root on the host."
        )
        assert any(tag["name"] == "operations" for tag in schema["tags"])

    def test_given_docs_route_when_fetching_then_serves_swagger_ui(self):
        client = TestClient(app)

        response = client.get("/docs")

        assert response.status_code == 200
        assert "Swagger UI" in response.text
