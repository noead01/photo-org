# Seed Corpus Development Load Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a checked-in offline seed corpus plus a deterministic validation and load path that the end-to-end suite can use as its fixed input dataset.

**Architecture:** Keep the corpus as a root-level repository asset with a machine-readable manifest and explicit licensing metadata, add CLI-backed validation and load commands so contributors can prepare the corpus through one documented path, and introduce an initial pytest e2e slice that proves ingest, queue processing, and metadata-backed search work repeatably against the real files. Synthetic fixtures remain unchanged for unit and BDD coverage.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, uv workspace, pytest, JSON manifest, checked-in photo fixtures

---

### Task 1: Add the checked-in seed corpus and manifest contract

**Files:**
- Create: `seed-corpus/README.md`
- Create: `seed-corpus/manifest.json`
- Create: `seed-corpus/family-events/birthday-park/` with checked-in photo assets referenced by the manifest
- Create: `seed-corpus/family-events/lake-weekend/` with checked-in photo assets referenced by the manifest
- Create: `seed-corpus/travel/city-break/` with checked-in photo assets referenced by the manifest
- Create: `seed-corpus/reference-faces/` with checked-in photo assets referenced by the manifest
- Create: `seed-corpus/misc/no-exif/` with checked-in photo assets referenced by the manifest
- Test: `apps/api/tests/test_seed_corpus_manifest.py`

- [ ] **Step 1: Write the failing corpus-manifest tests**

```python
import json
from pathlib import Path


def test_seed_corpus_manifest_describes_checked_in_assets():
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "seed-corpus" / "manifest.json"

    data = json.loads(manifest_path.read_text())

    assert data["version"] == 1
    assert data["root"] == "seed-corpus"
    assert len(data["assets"]) >= 20


def test_seed_corpus_assets_exist_and_include_required_metadata():
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "seed-corpus" / "manifest.json"
    data = json.loads(manifest_path.read_text())

    for asset in data["assets"]:
        assert (repo_root / asset["path"]).is_file()
        assert asset["license"]["spdx"]
        assert asset["license"]["source_url"]
        assert asset["expected"]["format"] in {"jpg", "jpeg", "png", "heic", "heif"}
        assert isinstance(asset["scenario_tags"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_seed_corpus_manifest.py -q`
Expected: FAIL because the seed corpus directory and manifest do not exist yet.

- [ ] **Step 3: Add the initial checked-in corpus, README, and manifest**

```json
{
  "version": 1,
  "root": "seed-corpus",
  "assets": [
    {
      "asset_id": "birthday_park_001",
      "path": "seed-corpus/family-events/birthday-park/birthday_park_001.jpg",
      "scenario_tags": ["ingest", "search", "face-bearing", "event:birthday"],
      "license": {
        "spdx": "CC0-1.0",
        "source_url": "https://example.invalid/source/birthday_park_001",
        "attribution": null
      },
      "expected": {
        "format": "jpg",
        "has_exif": true,
        "has_faces": true,
        "supports_face_labeling": true,
        "camera_make": "Canon",
        "shot_ts": "2022-06-14T15:20:00+00:00"
      }
    }
  ]
}
```

Add enough checked-in assets to satisfy the agreed shape:

- 20 to 50 photos total
- nested subfolders under the root corpus directory
- mixed file formats
- mixed EXIF coverage
- face-bearing and no-face images
- legally safe redistribution status recorded for every asset

- [ ] **Step 4: Run the manifest tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_seed_corpus_manifest.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add seed-corpus apps/api/tests/test_seed_corpus_manifest.py
git commit -m "feat(fixtures): add checked-in seed corpus manifest"
```

### Task 2: Add seed-corpus validation and load commands to the CLI workflow

**Files:**
- Create: `apps/api/app/dev/seed_corpus.py`
- Modify: `apps/api/app/cli.py`
- Modify: `scripts/photo-org`
- Modify: `Makefile`
- Test: `apps/api/tests/test_seed_corpus_cli.py`

- [ ] **Step 1: Write the failing CLI and validation tests**

```python
from pathlib import Path

from app.cli import main


def test_seed_corpus_validate_cli_succeeds_for_checked_in_manifest(capsys):
    exit_code = main(["seed-corpus", "validate"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "assets_validated=" in captured.out
    assert "validation=ok" in captured.out


def test_seed_corpus_load_cli_runs_migrate_ingest_and_queue_processing(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'seed-corpus.db'}"
    calls = []

    monkeypatch.setattr("app.cli.upgrade_database", lambda url: calls.append(("migrate", url)))
    monkeypatch.setattr("app.cli.ingest_directory", lambda *args, **kwargs: calls.append(("ingest", kwargs["database_url"])) or type("Result", (), {"scanned": 24, "enqueued": 24, "inserted": 0, "updated": 0, "errors": []})())
    monkeypatch.setattr("app.cli.load_seed_corpus_into_database", lambda **kwargs: calls.append(("load", kwargs["database_url"])) or {"processed": 24})

    exit_code = main(["seed-corpus", "load", "--database-url", db_url])

    assert exit_code == 0
    assert calls[0] == ("migrate", db_url)
    assert ("load", db_url) in calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_seed_corpus_cli.py -q`
Expected: FAIL because the `seed-corpus` CLI command group and helper module do not exist.

- [ ] **Step 3: Implement the seed-corpus helper module and CLI commands**

```python
@dataclass(frozen=True)
class SeedCorpusValidationReport:
    asset_count: int
    errors: list[str]


def validate_seed_corpus(corpus_root: Path | None = None) -> SeedCorpusValidationReport:
    manifest = load_seed_corpus_manifest(corpus_root)
    errors = []
    for asset in manifest.assets:
        if not asset.absolute_path.is_file():
            errors.append(f"missing file: {asset.path}")
        if not asset.license.spdx:
            errors.append(f"missing license spdx: {asset.asset_id}")
    return SeedCorpusValidationReport(asset_count=len(manifest.assets), errors=errors)


def load_seed_corpus_into_database(*, database_url: str | None = None, queue_limit: int = 100) -> dict[str, int]:
    corpus_root = resolve_seed_corpus_root()
    ingest_result = ingest_directory(corpus_root, database_url=database_url, queue_commit_chunk_size=queue_limit)
    processed = 0
    while True:
        batch = process_pending_ingest_queue(database_url, limit=queue_limit)
        processed += batch.processed
        if batch.processed == 0 and batch.retryable_errors == 0:
            break
    return {"scanned": ingest_result.scanned, "enqueued": ingest_result.enqueued, "processed": processed}
```

Extend the CLI to support:

```text
photo-org seed-corpus validate
photo-org seed-corpus load [--database-url ...] [--queue-limit 100]
```

Expose the documented workflow in `Makefile` with stable targets such as:

```make
seed-corpus-check:
	./scripts/photo-org seed-corpus validate

seed-corpus-load:
	./scripts/photo-org seed-corpus load
```

- [ ] **Step 4: Run the CLI tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_seed_corpus_cli.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/dev/seed_corpus.py apps/api/app/cli.py scripts/photo-org Makefile apps/api/tests/test_seed_corpus_cli.py
git commit -m "feat(dev): add seed corpus validation and load commands"
```

### Task 3: Add the first authoritative e2e slice backed by the seed corpus

**Files:**
- Create: `apps/api/tests/e2e/conftest.py`
- Create: `apps/api/tests/e2e/test_seed_corpus_workflow.py`
- Modify: `Makefile`

- [ ] **Step 1: Write the failing e2e test**

```python
from fastapi.testclient import TestClient

from app.main import app
from app.dev.seed_corpus import resolve_seed_corpus_root, validate_seed_corpus
from app.services.ingest_queue_processor import process_pending_ingest_queue


def test_seed_corpus_can_be_ingested_and_queried_end_to_end(seed_corpus_database_url, monkeypatch):
    report = validate_seed_corpus()
    assert report.errors == []

    load_result = load_seed_corpus_into_database(database_url=seed_corpus_database_url, queue_limit=10)
    assert load_result["processed"] >= 20

    client = TestClient(app)
    response = client.post(
        "/api/v1/search",
        json={
            "filters": {"camera_make": ["Canon"]},
            "sort": {"by": "shot_ts", "dir": "desc"},
            "page": {"limit": 10}
        },
    )

    assert response.status_code == 200
    assert response.json()["hits"]["total"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/e2e/test_seed_corpus_workflow.py -q`
Expected: FAIL because the e2e fixture wiring and corpus load path are not implemented yet.

- [ ] **Step 3: Implement the initial e2e fixture wiring**

```python
@pytest.fixture
def seed_corpus_database_url(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'seed-corpus-e2e.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    app.dependency_overrides.clear()
    yield database_url
    app.dependency_overrides.clear()
```

Make the e2e slice assert real, stable corpus-backed behavior:

- corpus validation passes
- database migration and ingest complete
- queue processing drains the pending rows
- at least one representative metadata-backed search returns known assets from the manifest

Add a dedicated Make target:

```make
test-e2e:
	$(PYTEST) apps/api/tests/e2e -q
```

- [ ] **Step 4: Run the e2e test to verify it passes**

Run: `uv run pytest apps/api/tests/e2e/test_seed_corpus_workflow.py -q`
Expected: PASS

- [ ] **Step 5: Run the dedicated e2e command path**

Run: `make test-e2e`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/api/tests/e2e/conftest.py apps/api/tests/e2e/test_seed_corpus_workflow.py Makefile
git commit -m "test(e2e): add seed corpus workflow validation"
```

### Task 4: Document the contributor workflow and corpus contract

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/ITERATIVE_DEVELOPMENT.md`
- Modify: `seed-corpus/README.md`

- [ ] **Step 1: Write the failing documentation-oriented assertions**

```python
from pathlib import Path


def test_seed_corpus_docs_reference_make_targets_and_fixture_boundary():
    contributing = Path("CONTRIBUTING.md").read_text()
    iterative = Path("docs/ITERATIVE_DEVELOPMENT.md").read_text()

    assert "make seed-corpus-check" in contributing
    assert "make seed-corpus-load" in contributing
    assert "make test-e2e" in contributing
    assert "Synthetic fixtures remain preferred for unit tests and BDD scenarios." in iterative
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_seed_corpus_manifest.py::test_seed_corpus_docs_reference_make_targets_and_fixture_boundary -q`
Expected: FAIL because the docs do not yet describe the new workflow or the corpus-vs-synthetic boundary.

- [ ] **Step 3: Update the docs**

Document these points explicitly:

- the checked-in corpus lives under `seed-corpus/`
- every asset must be safe to redistribute and have source/license metadata recorded
- contributors should use `make seed-corpus-check` and `make seed-corpus-load`
- `make test-e2e` is the initial authoritative real-file workflow
- unit tests and BDD scenarios should continue using synthetic fixtures

- [ ] **Step 4: Run the documentation assertion and the focused test slice**

Run: `uv run pytest apps/api/tests/test_seed_corpus_manifest.py::test_seed_corpus_docs_reference_make_targets_and_fixture_boundary -q`
Expected: PASS

Run: `make test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md CONTRIBUTING.md docs/ITERATIVE_DEVELOPMENT.md seed-corpus/README.md apps/api/tests/test_seed_corpus_manifest.py
git commit -m "docs: describe seed corpus workflow"
```

### Task 5: Run the full verification path for issue #19

**Files:**
- Modify: `Makefile` if any final target adjustments are still needed

- [ ] **Step 1: Run the corpus validation workflow**

Run: `make seed-corpus-check`
Expected: PASS with a validated asset count and no manifest errors.

- [ ] **Step 2: Run the corpus load workflow**

Run: `./scripts/photo-org seed-corpus load --database-url apps/api/photoorg-seed.db`
Expected: PASS with migrated schema, successful ingest summary, and queue rows fully processed.

- [ ] **Step 3: Run the authoritative e2e suite**

Run: `make test-e2e`
Expected: PASS

- [ ] **Step 4: Run the existing focused regression slice**

Run: `make test`
Expected: PASS

- [ ] **Step 5: Commit any final workflow fixups**

```bash
git add Makefile
git commit -m "chore(dev): finalize seed corpus workflow targets"
```
