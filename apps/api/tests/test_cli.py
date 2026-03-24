import os
import subprocess
import sys
from pathlib import Path

from app.cli import main
from app.migrations import upgrade_database


def _resolve_samples_dir() -> Path:
    test_file = Path(__file__).resolve()
    for parent in test_file.parents:
        candidate = parent / "seed-corpus" / "family-events" / "birthday-park"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not locate seed-corpus/family-events/birthday-park from test_cli.py")


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
    assert len(calls) == 3
    assert [call["limit"] for call in calls] == [2, 2, 2]


def test_cli_module_executes_main_when_run_with_dash_m(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'cli-module.db'}"
    repo_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "apps" / "api")

    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "migrate", "--database-url", db_url],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert f"database_url={db_url}" in result.stdout
    assert "migration=head" in result.stdout
