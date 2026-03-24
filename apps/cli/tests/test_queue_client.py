from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace


def _import_queue_client(monkeypatch):
    repo_root = __import__("pathlib").Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(repo_root / "apps" / "api"))
    monkeypatch.syspath_prepend(str(repo_root / "apps" / "cli"))
    for module_name in ("cli", "cli.queue_client", "app.dev.seed_corpus", "app.processing.ingest"):
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()
    return importlib.import_module("cli.queue_client")


def test_enqueue_directory_delegates_to_ingest_directory(monkeypatch, tmp_path):
    queue_client = _import_queue_client(monkeypatch)
    calls: list[tuple[object, dict]] = []
    face_detector = object()

    monkeypatch.setattr(
        queue_client,
        "ingest_directory",
        lambda root, **kwargs: calls.append((root, kwargs))
        or SimpleNamespace(scanned=4, enqueued=4, inserted=0, updated=0, errors=[]),
    )

    result = queue_client.enqueue_directory(
        tmp_path,
        database_url="sqlite:///cli.db",
        face_detector=face_detector,
    )

    assert result.enqueued == 4
    assert calls == [
        (
            tmp_path,
            {
                "database_url": "sqlite:///cli.db",
                "face_detector": face_detector,
            },
        )
    ]


def test_load_seed_corpus_into_queue_delegates_to_seed_loader(monkeypatch):
    queue_client = _import_queue_client(monkeypatch)
    calls: list[dict] = []

    monkeypatch.setattr(
        queue_client,
        "load_seed_corpus_into_database",
        lambda **kwargs: calls.append(kwargs)
        or {"scanned": 12, "enqueued": 12, "processed": 0},
    )

    result = queue_client.load_seed_corpus_into_queue(
        database_url="sqlite:///seed.db",
    )

    assert result == {"scanned": 12, "enqueued": 12, "processed": 0}
    assert calls == [{"database_url": "sqlite:///seed.db"}]
