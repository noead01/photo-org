import json
from pathlib import Path

from app.cli import main
import app.dev.seed_corpus as seed_corpus
from app.dev.seed_corpus import load_seed_corpus_into_database, resolve_seed_corpus_root, validate_seed_corpus


def test_seed_corpus_validate_cli_succeeds_for_checked_in_manifest(capsys):
    exit_code = main(["seed-corpus", "validate"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "assets_validated=" in captured.out
    assert "validation=ok" in captured.out


def test_resolve_seed_corpus_root_tracks_worktree_layout(tmp_path, monkeypatch):
    worktree_root = tmp_path / "repo" / ".worktrees" / "issue-18-compose-dev-stack"
    seed_corpus_dir = worktree_root / "seed-corpus"
    seed_corpus_dir.mkdir(parents=True)

    fake_module_file = worktree_root / "apps" / "api" / "app" / "dev" / "seed_corpus.py"
    fake_module_file.parent.mkdir(parents=True)
    fake_module_file.write_text("")

    monkeypatch.setattr(seed_corpus, "__file__", str(fake_module_file))

    assert resolve_seed_corpus_root() == seed_corpus_dir


def test_seed_corpus_load_cli_runs_migrate_and_corpus_loader(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'seed-corpus.db'}"
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "app.cli.upgrade_database",
        lambda url: calls.append(("migrate", url)),
    )
    monkeypatch.setattr(
        "app.cli.load_seed_corpus_into_database",
        lambda **kwargs: calls.append(("load", kwargs["database_url"]))
        or {"scanned": 24, "enqueued": 24, "processed": 0},
    )

    exit_code = main(["seed-corpus", "load", "--database-url", database_url])

    assert exit_code == 0
    assert calls == [("migrate", database_url), ("load", database_url)]


def test_validate_seed_corpus_reports_duplicate_file_content(tmp_path):
    corpus_root = tmp_path / "seed-corpus"
    corpus_root.mkdir()
    first = corpus_root / "first.jpg"
    second = corpus_root / "second.jpg"
    content = b"same-bytes"
    first.write_bytes(content)
    second.write_bytes(content)
    (corpus_root / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "root": "seed-corpus",
                "assets": [
                    {
                        "asset_id": "a1",
                        "path": "seed-corpus/first.jpg",
                        "scenario_tags": ["ingest"],
                        "license": {"spdx": "LicenseRef-Public-Domain", "source_url": "https://example.invalid/a1"},
                        "expected": {"format": "jpg", "has_exif": False, "has_faces": False, "supports_face_labeling": False},
                    },
                    {
                        "asset_id": "a2",
                        "path": "seed-corpus/second.jpg",
                        "scenario_tags": ["ingest"],
                        "license": {"spdx": "LicenseRef-Public-Domain", "source_url": "https://example.invalid/a2"},
                        "expected": {"format": "jpg", "has_exif": False, "has_faces": False, "supports_face_labeling": False},
                    },
                ],
            }
        )
    )

    report = validate_seed_corpus(corpus_root)

    assert report.asset_count == 2
    assert any("duplicate sha256" in error for error in report.errors)


def test_load_seed_corpus_into_database_uses_local_queue_loading(monkeypatch):
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        "app.dev.seed_corpus.validate_seed_corpus",
        lambda corpus_root=None: type("Report", (), {"errors": [], "asset_count": 24})(),
    )
    monkeypatch.setattr(
        "app.dev.seed_corpus.ingest_directory",
        lambda *args, **kwargs: calls.append(("ingest", kwargs))
        or type(
            "Result",
            (),
            {"scanned": 24, "enqueued": 24, "inserted": 0, "updated": 0, "errors": []},
        )(),
    )

    result = load_seed_corpus_into_database(database_url="sqlite:///seed.db")

    assert result == {"scanned": 24, "enqueued": 24, "processed": 0}
    assert calls[0][0] == "ingest"
    assert calls[0][1] == {
        "database_url": "sqlite:///seed.db",
    }
    assert calls[1:] == []
