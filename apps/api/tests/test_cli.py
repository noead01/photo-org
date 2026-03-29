import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from app.cli import main
from app.migrations import upgrade_database
from app.services.source_registration import MARKER_FILENAME
from app.services.storage_sources import attach_storage_source_alias, create_storage_source
from app.services.watched_folders import create_watched_folder
from app.storage import photos, storage_sources


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
SEED_CORPUS_CONTAINER_PATH = "/photos/seed-corpus"


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


def test_ingest_cli_is_not_supported_anymore(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _use_supported_cli_runtime(monkeypatch)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'cli-ingest.db'}"
    upgrade_database(db_url)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "ingest",
                str(staged_corpus_dir),
                "--database-url",
                db_url,
            ]
        )

    assert exc_info.value.code == 2


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


def test_poll_storage_sources_cli_scans_registered_watched_folders(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    _use_supported_cli_runtime(monkeypatch)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'cli-poll-storage-sources.db'}"
    upgrade_database(db_url)
    _seed_registered_storage_source_with_watched_folder(
        db_url,
        root_path=staged_corpus_dir,
        watched_path=staged_corpus_dir,
        display_name="Seed Corpus",
        now=datetime(2026, 3, 28, 22, 15, tzinfo=UTC),
    )

    exit_code = main(["poll-storage-sources", "--database-url", db_url])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "scanned=6" in output
    assert "inserted=6" in output
    assert "updated=0" in output
    assert "errors=0" in output

    engine = create_engine(db_url, future=True)
    with engine.connect() as connection:
        assert connection.execute(select(photos.c.photo_id)).first() is not None


def test_poll_storage_sources_cli_returns_nonzero_when_source_validation_fails(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    _use_supported_cli_runtime(monkeypatch)
    staged_corpus_dir = _stage_seed_corpus_subset(tmp_path)
    db_url = f"sqlite:///{tmp_path / 'cli-poll-storage-sources-error.db'}"
    upgrade_database(db_url)
    source_id = _seed_registered_storage_source_with_watched_folder(
        db_url,
        root_path=staged_corpus_dir,
        watched_path=staged_corpus_dir,
        display_name="Seed Corpus",
        now=datetime(2026, 3, 28, 22, 20, tzinfo=UTC),
    )
    (staged_corpus_dir / MARKER_FILENAME).unlink()

    exit_code = main(["poll-storage-sources", "--database-url", db_url])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "errors=1" in output
    assert f"storage_source:{source_id}: storage source marker file is missing" in output

    engine = create_engine(db_url, future=True)
    with engine.connect() as connection:
        source = connection.execute(
            select(storage_sources).where(storage_sources.c.storage_source_id == source_id)
        ).mappings().one()
    assert source["last_failure_reason"] == "marker_missing"


def _seed_registered_storage_source_with_watched_folder(
    database_url: str,
    *,
    root_path: Path,
    watched_path: Path,
    display_name: str,
    now: datetime,
) -> str:
    root = root_path.resolve()
    watched = watched_path.resolve()
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name=display_name,
            marker_filename=MARKER_FILENAME,
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            now=now,
        )
        (root / MARKER_FILENAME).write_text(
            f'{{"storage_source_id":"{source["storage_source_id"]}","marker_version":1}}'
        )
        create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=root.as_posix(),
            watched_path=watched.as_posix(),
            display_name=display_name,
            now=now,
        )
    return str(source["storage_source_id"])
