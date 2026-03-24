import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_seed_corpus_manifest_describes_checked_in_assets():
    manifest_path = _repo_root() / "seed-corpus" / "manifest.json"

    data = json.loads(manifest_path.read_text())

    assert data["version"] == 1
    assert data["root"] == "seed-corpus"
    assert len(data["assets"]) >= 20


def test_seed_corpus_assets_exist_and_include_required_metadata():
    manifest_path = _repo_root() / "seed-corpus" / "manifest.json"
    data = json.loads(manifest_path.read_text())

    for asset in data["assets"]:
        assert (_repo_root() / asset["path"]).is_file()
        assert asset["license"]["spdx"]
        assert asset["license"]["source_url"]
        assert asset["expected"]["format"] in {"jpg", "jpeg", "png", "heic", "heif"}
        assert isinstance(asset["scenario_tags"], list)


def test_seed_corpus_docs_reference_make_targets_and_fixture_boundary():
    contributing = (_repo_root() / "CONTRIBUTING.md").read_text()
    readme = (_repo_root() / "README.md").read_text()
    iterative = (_repo_root() / "docs" / "ITERATIVE_DEVELOPMENT.md").read_text()
    gitignore = (_repo_root() / ".gitignore").read_text()

    assert "## Baseline Phase 0 Workflow" in contributing
    assert "1. `make sync`" in contributing
    assert "2. `make migrate` when a local database is needed" in contributing
    assert "3. `make seed-corpus-check`" in contributing
    assert "4. `make seed-corpus-load`" in contributing
    assert "5. `make check`" in contributing
    assert "6. `make test-all` and `make test-e2e` before broader changes or handoff" in contributing
    assert "The repo assumes local Python development through `uv`." in contributing
    assert "make seed-corpus-check" in contributing
    assert "make seed-corpus-load" in contributing
    assert "make test-e2e" in contributing
    assert "Generated local artifacts should go under `.local/`." in contributing
    assert "Compose-based stack startup is not yet the supported baseline contributor workflow." in contributing
    assert "For contributor setup and validation commands, see [CONTRIBUTING.md](CONTRIBUTING.md)." in readme
    assert ".local/" in gitignore
    assert "Synthetic fixtures remain preferred for unit tests and BDD scenarios." in iterative
