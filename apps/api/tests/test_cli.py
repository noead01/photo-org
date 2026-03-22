from pathlib import Path

from app.cli import main
from app.migrations import upgrade_database


def _resolve_samples_dir() -> Path:
    test_file = Path(__file__).resolve()
    for parent in test_file.parents:
        candidate = parent / "apps" / "api" / "features" / "samples"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not locate apps/api/features/samples from test_cli.py")


SAMPLES_DIR = _resolve_samples_dir()


def test_ingest_cli_triggers_queue_processing_when_chunk_threshold_is_reached(
    monkeypatch,
    tmp_path,
):
    db_url = f"sqlite:///{tmp_path / 'cli-ingest.db'}"
    calls: list[dict] = []
    upgrade_database(db_url)

    monkeypatch.setattr(
        "app.services.worker_queue_trigger.trigger_queue_processing",
        lambda **kwargs: calls.append(kwargs),
    )

    exit_code = main(
        [
            "ingest",
            str(SAMPLES_DIR),
            "--database-url",
            db_url,
            "--queue-commit-chunk-size",
            "2",
        ]
    )

    assert exit_code == 0
    assert len(calls) == 5
    assert [call["limit"] for call in calls] == [2, 2, 2, 2, 2]
