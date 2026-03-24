import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.cli import main
from app.db.queue import IngestQueueStore
from app.migrations import upgrade_database


def _resolve_seed_corpus_dir(start: Path | None = None) -> Path:
    test_file = (start or Path(__file__)).resolve()
    for parent in [test_file.parent, *test_file.parents]:
        candidate = parent / "seed-corpus"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not locate seed-corpus from test_cli.py")


SEED_CORPUS_DIR = _resolve_seed_corpus_dir()
SEED_CORPUS_SUBSET_PATHS = (
    "seed-corpus/family-events/birthday-park/birthday_park_001.jpg",
    "seed-corpus/family-events/birthday-park/birthday_park_002.jpeg",
    "seed-corpus/family-events/birthday-park/birthday_park_003.heic",
    "seed-corpus/family-events/birthday-park/birthday_park_004.png",
    "seed-corpus/family-events/birthday-park/birthday_park_005.jpg",
    "seed-corpus/family-events/birthday-park/birthday_park_006.jpg",
)


def test_resolve_seed_corpus_dir_finds_a_worktree_layout(tmp_path):
    repo_root = tmp_path / "repo"
    seed_corpus_dir = repo_root / "seed-corpus"
    seed_corpus_dir.mkdir(parents=True)

    worktree_test_file = repo_root / ".worktrees" / "issue-18-compose-dev-stack" / "apps" / "api" / "tests" / "test_cli.py"
    worktree_test_file.parent.mkdir(parents=True)
    worktree_test_file.write_text("")

    assert _resolve_seed_corpus_dir(worktree_test_file) == seed_corpus_dir


def _stage_seed_corpus_subset(destination_root: Path) -> Path:
    staged_root = destination_root / "seed-corpus"
    for asset_path in SEED_CORPUS_SUBSET_PATHS:
        relative_path = asset_path.removeprefix("seed-corpus/")
        source = SEED_CORPUS_DIR / relative_path
        target = staged_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return staged_root


def _use_supported_cli_runtime(monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(repo_root / "apps" / "api"))
    monkeypatch.syspath_prepend(str(repo_root / "apps" / "cli"))


def test_ingest_cli_enqueues_photos_into_queue(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _use_supported_cli_runtime(monkeypatch)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'cli-ingest.db'}"
    upgrade_database(db_url)

    exit_code = main(
        [
            "ingest",
            str(staged_corpus_dir),
            "--database-url",
            db_url,
        ]
    )

    assert exit_code == 0
    assert len(IngestQueueStore(db_url).list_pending()) == 6


def test_ingest_cli_requires_the_queue_client_package(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'cli-ingest.db'}"
    upgrade_database(db_url)
    monkeypatch.setattr("app.cli.Path.is_file", lambda self: False)

    def missing_queue_client(module_name):
        raise ModuleNotFoundError(name="cli.queue_client")

    monkeypatch.setattr("app.cli.import_module", missing_queue_client)

    try:
        main(
            [
                "ingest",
                str(staged_corpus_dir),
                "--database-url",
                db_url,
            ]
        )
    except ModuleNotFoundError as exc:
        assert exc.name == "cli.queue_client"
    else:
        raise AssertionError("expected queue-client import to fail fast")


def test_load_queue_client_imports_the_cli_queue_client(monkeypatch):
    import app.cli as api_cli

    sentinel = object()
    expected_path = (
        Path(api_cli.__file__).resolve().parents[3]
        / "apps"
        / "cli"
        / "cli"
        / "queue_client.py"
    )
    monkeypatch.setattr(api_cli.Path, "is_file", lambda self: self == expected_path)
    monkeypatch.setattr(
        api_cli.importlib.util,
        "spec_from_file_location",
        lambda name, path: type("Spec", (), {"loader": type("Loader", (), {"exec_module": lambda self, module: None})()})()
        if path == expected_path and name == "photoorg_cli_queue_client"
        else None,
    )
    monkeypatch.setattr(api_cli.importlib.util, "module_from_spec", lambda spec: sentinel)

    queue_client = api_cli._load_queue_client()

    assert queue_client is sentinel


def test_load_queue_client_propagates_unrelated_missing_import(monkeypatch):
    import app.cli as api_cli

    monkeypatch.setattr("app.cli.Path.is_file", lambda self: False)

    def missing_dependency(module_name):
        raise ModuleNotFoundError(name="app.processing.missing_dependency")

    monkeypatch.setattr(api_cli, "import_module", missing_dependency)

    try:
        api_cli._load_queue_client()
    except ModuleNotFoundError as exc:
        assert exc.name == "app.processing.missing_dependency"
    else:
        raise AssertionError("expected ModuleNotFoundError to propagate")


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
