from __future__ import annotations

from datetime import UTC, datetime

from app.migrations import upgrade_database


def test_poll_registered_storage_sources_returns_empty_result_for_empty_database(tmp_path):
    from app.processing.ingest_polling import poll_registered_storage_sources

    database_url = f"sqlite:///{tmp_path / 'poll-empty.db'}"
    upgrade_database(database_url)

    result = poll_registered_storage_sources(
        database_url=database_url,
        now=datetime(2026, 3, 29, 0, 0, tzinfo=UTC),
    )

    assert result.scanned == 0
    assert result.inserted == 0
    assert result.updated == 0
    assert result.errors == []
