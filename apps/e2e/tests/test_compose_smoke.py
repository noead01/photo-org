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
