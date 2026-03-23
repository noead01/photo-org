import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from app.main import app


@pytest.fixture
def seed_corpus_database_url(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'seed-corpus-e2e.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    app.dependency_overrides.clear()
    yield database_url
    app.dependency_overrides.clear()
