import yaml
from fastapi.testclient import TestClient

from app.main import app
from app.openapi_docs import OPENAPI_YAML_MEDIA_TYPE, render_openapi_yaml, write_openapi_yaml


def test_openapi_yaml_route_returns_yaml_equivalent_to_runtime_schema():
    client = TestClient(app)

    json_schema = client.get("/openapi.json")
    yaml_schema = client.get("/openapi.yaml")

    assert json_schema.status_code == 200
    assert yaml_schema.status_code == 200
    assert yaml_schema.headers["content-type"].startswith(OPENAPI_YAML_MEDIA_TYPE)
    assert yaml.safe_load(yaml_schema.text) == json_schema.json()


def test_openapi_docs_route_serves_swagger_ui():
    client = TestClient(app)

    response = client.get("/docs")

    assert response.status_code == 200
    assert "Swagger UI" in response.text


def test_openapi_yaml_renderer_preserves_runtime_schema_shape():
    rendered = render_openapi_yaml(app.openapi())
    assert yaml.safe_load(rendered) == app.openapi()


def test_openapi_generator_writes_yaml_file(tmp_path):
    output_path = tmp_path / "openapi.yaml"

    written_path = write_openapi_yaml(app.openapi(), output_path)

    assert written_path == output_path
    assert yaml.safe_load(output_path.read_text()) == app.openapi()
