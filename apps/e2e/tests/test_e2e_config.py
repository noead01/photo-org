import pytest

from conftest import seed_corpus_api_base_url, seed_corpus_database_url


def test_seed_corpus_database_url_prefers_existing_database_url_env(monkeypatch, tmp_path):
    expected = "postgresql+psycopg://photoorg:photoorg@localhost:55432/photoorg"
    monkeypatch.setenv("PHOTO_ORG_E2E_DATABASE_URL", expected)

    fixture = seed_corpus_database_url.__wrapped__
    generator = fixture(tmp_path, monkeypatch)
    try:
        database_url = next(generator)
        assert database_url == expected
    finally:
        with pytest.raises(StopIteration):
            next(generator)


def test_seed_corpus_api_base_url_prefers_existing_api_base_url_env(monkeypatch):
    expected = "http://localhost:55123"
    monkeypatch.setenv("PHOTO_ORG_E2E_API_BASE_URL", expected)

    fixture = seed_corpus_api_base_url.__wrapped__

    assert fixture() == expected
