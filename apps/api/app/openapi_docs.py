from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import Response


OPENAPI_YAML_MEDIA_TYPE = "application/yaml"


def render_openapi_yaml(schema: dict) -> str:
    return yaml.safe_dump(schema, sort_keys=False, allow_unicode=False)


def openapi_yaml_response(schema: dict) -> Response:
    return Response(content=render_openapi_yaml(schema), media_type=OPENAPI_YAML_MEDIA_TYPE)


def write_openapi_yaml(schema: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_openapi_yaml(schema), encoding="utf-8")
    return output_path
