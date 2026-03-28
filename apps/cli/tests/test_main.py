from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def _import_cli_modules(monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(repo_root / "apps" / "api"))
    monkeypatch.syspath_prepend(str(repo_root / "apps" / "cli"))
    for module_name in ("cli", "cli.main", "cli.__main__", "app.cli"):
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()
    api_cli = importlib.import_module("app.cli")
    cli_main = importlib.import_module("cli.main")
    return cli_main, api_cli


def test_cli_wrapper_delegates_build_parser(monkeypatch):
    cli_main, api_cli = _import_cli_modules(monkeypatch)
    sentinel = object()

    monkeypatch.setattr(api_cli, "build_parser", lambda: sentinel)

    assert cli_main.build_parser() is sentinel


def test_cli_wrapper_delegates_main(monkeypatch):
    cli_main, api_cli = _import_cli_modules(monkeypatch)

    monkeypatch.setattr(api_cli, "main", lambda argv=None: argv)

    assert cli_main.main(["migrate"]) == ["migrate"]


def test_ingest_command_is_not_supported_anymore(monkeypatch, tmp_path):
    cli_main, api_cli = _import_cli_modules(monkeypatch)
    monkeypatch.setattr(api_cli, "resolve_database_url", lambda database_url: database_url)

    try:
        cli_main.main(["ingest", str(tmp_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected ingest command to be rejected")


def test_seed_corpus_load_command_parses_database_url(monkeypatch):
    cli_main, api_cli = _import_cli_modules(monkeypatch)
    calls: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        api_cli,
        "upgrade_database",
        lambda database_url: calls.append(("upgrade", {"database_url": database_url})),
    )
    monkeypatch.setattr(
        api_cli,
        "load_seed_corpus_into_database",
        lambda **kwargs: calls.append(("load", kwargs))
        or {"scanned": 2, "enqueued": 2, "processed": 0},
    )
    monkeypatch.setattr(api_cli, "resolve_database_url", lambda database_url: database_url)

    exit_code = cli_main.main(
        [
            "seed-corpus",
            "load",
            "--database-url",
            "sqlite:///seed.db",
        ]
    )

    assert exit_code == 0
    assert calls == [
        ("upgrade", {"database_url": "sqlite:///seed.db"}),
        ("load", {"database_url": "sqlite:///seed.db"}),
    ]


def test_migrate_command_parses_database_url(monkeypatch, capsys):
    cli_main, api_cli = _import_cli_modules(monkeypatch)
    calls: list[str | None] = []

    monkeypatch.setattr(api_cli, "upgrade_database", lambda database_url: calls.append(database_url))
    monkeypatch.setattr(api_cli, "resolve_database_url", lambda database_url: database_url)

    exit_code = cli_main.main(["migrate", "--database-url", "sqlite:///migrate.db"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == ["sqlite:///migrate.db"]
    assert "database_url=sqlite:///migrate.db" in captured.out
    assert "migration=head" in captured.out


def test_script_help_text_exposes_expected_commands():
    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        ["./scripts/photo-org", "--help"],
        cwd=repo_root,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "seed-corpus" in result.stdout
    assert "migrate" in result.stdout
    assert "ingest" not in result.stdout
    assert "triggering queue processing" not in result.stdout
