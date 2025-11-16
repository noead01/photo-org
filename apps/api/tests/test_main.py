import pytest
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