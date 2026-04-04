import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from app.main import app


@pytest.fixture
def seed_corpus_database_url(tmp_path, monkeypatch):
    database_url = os.getenv("PHOTO_ORG_E2E_DATABASE_URL") or f"sqlite:///{tmp_path / 'seed-corpus-e2e.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    app.dependency_overrides.clear()
    yield database_url
    app.dependency_overrides.clear()


@pytest.fixture
def seed_corpus_api_base_url() -> str | None:
    return os.getenv("PHOTO_ORG_E2E_API_BASE_URL")


@pytest.fixture
def deployment_api_client(seed_corpus_api_base_url: str | None):
    if not seed_corpus_api_base_url:
        pytest.skip("deployment-facing API tests require PHOTO_ORG_E2E_API_BASE_URL")

    with httpx.Client(base_url=seed_corpus_api_base_url, timeout=30.0) as client:
        yield client
