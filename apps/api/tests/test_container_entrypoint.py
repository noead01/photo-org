import importlib.util
from pathlib import Path

import pytest


def _load_entrypoint_module():
    entrypoint_path = Path(__file__).resolve().parents[1] / "docker" / "entrypoint.py"
    spec = importlib.util.spec_from_file_location("api_container_entrypoint", entrypoint_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_entrypoint = _load_entrypoint_module().run_entrypoint


def test_entrypoint_runs_migrations_before_starting_server(monkeypatch):
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "app.migrations.upgrade_database",
        lambda url: calls.append(("migrate", url)),
    )
    monkeypatch.setattr(
        "uvicorn.run",
        lambda *args, **kwargs: calls.append(("serve", kwargs["host"])),
    )

    run_entrypoint(database_url="postgresql://photoorg@db/photoorg")

    assert calls == [
        ("migrate", "postgresql://photoorg@db/photoorg"),
        ("serve", "0.0.0.0"),
    ]


def test_entrypoint_exits_without_serving_when_migration_fails(monkeypatch):
    def fail_migration(url):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.migrations.upgrade_database", fail_migration)
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: pytest.fail("server should not start"))

    with pytest.raises(SystemExit) as excinfo:
        run_entrypoint(database_url="postgresql://photoorg@db/photoorg")

    assert excinfo.value.code == 1
