from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from app.main import app


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

    def test_given_openapi_schema_when_fetching_then_excludes_search_route_and_keeps_health_route(self):
        """
        Given: The runtime OpenAPI schema
        When: Fetching /openapi.json
        Then: Search is no longer exposed and health remains available
        """
        client = TestClient(app)

        response = client.get("/openapi.json")

        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/api/v1/search" not in paths
        assert "/healthz" in paths

    def test_given_checked_in_openapi_when_compared_to_runtime_then_matches_current_fastapi_schema(self):
        """
        Given: The checked-in OpenAPI contract
        When: Comparing it to the runtime schema
        Then: The contract matches the current FastAPI app exactly
        """
        client = TestClient(app)
        runtime = client.get("/openapi.json").json()
        checked_in = yaml.safe_load(
            Path(__file__).resolve().parents[1].joinpath("openapi", "spec.yaml").read_text()
        )

        assert checked_in == runtime

    def test_given_storage_source_registration_route_when_fetching_openapi_then_declares_400_response(self):
        """
        Given: The storage source registration route
        When: Fetching the runtime OpenAPI schema
        Then: The route declares the documented 400 error response
        """
        client = TestClient(app)

        response = client.get("/openapi.json")

        assert response.status_code == 200
        operation = response.json()["paths"]["/api/v1/storage-sources"]["post"]
        assert "400" in operation["responses"]
