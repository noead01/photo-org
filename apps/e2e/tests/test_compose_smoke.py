from pathlib import Path


def test_makefile_documents_compose_targets():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "compose-up:" in makefile
    assert "compose-migrate:" in makefile
    assert "compose-down:" in makefile


def test_docs_point_to_compose_workflow():
    readme = Path("README.md").read_text(encoding="utf-8")
    contributing = Path("CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "make compose-up" in readme
    assert "compose-up" in contributing
    assert "compose-migrate" in contributing


def test_makefile_documents_compose_smoke_workflow():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    contributing = Path("CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "compose-smoke:" in makefile
    assert "./scripts/photo-org ingest seed-corpus" in makefile
    assert "/api/v1/internal/ingest-queue/process" in makefile
    assert "compose-smoke" in contributing
