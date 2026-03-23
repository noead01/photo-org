# Compose DB Service Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish Docker Compose as the default local runtime for `postgres + db-service`, move client commands into `apps/cli`, and remove legacy API surfaces that no longer match the DB-service boundary.

**Architecture:** Keep `apps/api` as the DB service that owns migrations, queue processing, and domain-table mutations. Create a real `apps/cli` package that owns ingest submission and queue-scoped operator workflows only. Add Compose and container entrypoint wiring so the DB service waits for PostgreSQL, applies migrations on startup, fails hard on migration errors, and serves only after the schema is ready.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Docker Compose, uv workspace, pytest

---

### Task 1: Fix worktree-sensitive fixture and path assumptions before larger changes

**Files:**
- Modify: `apps/api/tests/test_ingest.py`
- Modify: `apps/api/tests/test_cli.py`
- Modify: `apps/api/tests/test_seed_corpus_cli.py`
- Test: `apps/api/tests/test_ingest.py`
- Test: `apps/api/tests/test_cli.py`

- [ ] **Step 1: Write the failing path-resolution tests**

```python
def test_resolve_samples_dir_finds_repo_fixture_from_worktree():
    samples_dir = _resolve_samples_dir()
    assert samples_dir.name == "samples"
    assert samples_dir.joinpath("IMG_8172.jpg").exists()
```

- [ ] **Step 2: Run the focused tests to verify they fail in a worktree**

Run: `uv run pytest apps/api/tests/test_ingest.py apps/api/tests/test_cli.py -q`
Expected: FAIL with the current `FileNotFoundError` fixture lookup from the worktree path.

- [ ] **Step 3: Implement minimal repo-root-aware fixture resolution**

```python
def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError("Could not locate repo root")
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_ingest.py apps/api/tests/test_cli.py apps/api/tests/test_seed_corpus_cli.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/test_ingest.py apps/api/tests/test_cli.py apps/api/tests/test_seed_corpus_cli.py
git commit -m "test: make fixture lookup work from worktrees"
```

### Task 2: Create a real `apps/cli` package and move client-only commands into it

**Files:**
- Modify: `apps/cli/pyproject.toml`
- Create: `apps/cli/cli/__init__.py`
- Create: `apps/cli/cli/__main__.py`
- Create: `apps/cli/cli/main.py`
- Create: `apps/cli/tests/test_main.py`
- Modify: `scripts/photo-org`
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/app/__main__.py`

- [ ] **Step 1: Write the failing CLI-package tests**

```python
def test_cli_ingest_command_parses_database_url_and_root(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("cli.main.enqueue_ingest_directory", lambda **kwargs: calls.append(kwargs) or {"enqueued": 3})
    exit_code = main(["ingest", str(tmp_path), "--database-url", "postgresql://photoorg@localhost/photoorg"])
    assert exit_code == 0
    assert calls[0]["database_url"].startswith("postgresql://")


def test_cli_seed_corpus_load_keeps_processing_outside_direct_domain_writes(monkeypatch):
    calls = []
    monkeypatch.setattr("cli.main.load_seed_corpus_into_queue", lambda **kwargs: calls.append(kwargs) or {"scanned": 2, "enqueued": 2})
    assert main(["seed-corpus", "load"]) == 0
    assert calls[0]["process_queue"] is False
```

- [ ] **Step 2: Run the new CLI tests to verify they fail**

Run: `uv run pytest apps/cli/tests/test_main.py -q`
Expected: FAIL because the `apps/cli` package and entrypoints do not exist.

- [ ] **Step 3: Implement the minimal CLI package and move the script entrypoint**

```python
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "ingest":
        result = enqueue_ingest_directory(...)
        print(f"enqueued={result['enqueued']}")
        return 0
```

- [ ] **Step 4: Run the CLI tests to verify they pass**

Run: `uv run pytest apps/cli/tests/test_main.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/cli/pyproject.toml apps/cli/cli/__init__.py apps/cli/cli/__main__.py apps/cli/cli/main.py apps/cli/tests/test_main.py scripts/photo-org apps/api/pyproject.toml apps/api/app/__main__.py
git commit -m "feat(cli): move client commands into apps/cli"
```

### Task 3: Split queue submission from DB-service-owned processing

**Files:**
- Create: `apps/cli/cli/queue_client.py`
- Modify: `apps/api/app/processing/ingest.py`
- Modify: `apps/api/app/dev/seed_corpus.py`
- Modify: `apps/api/tests/test_ingest.py`
- Modify: `apps/api/tests/test_seed_corpus_cli.py`
- Create: `apps/cli/tests/test_queue_client.py`

- [ ] **Step 1: Write the failing queue-boundary tests**

```python
def test_enqueue_ingest_directory_only_writes_ingest_queue(tmp_path):
    database_url = migrated_database_url(tmp_path)
    result = enqueue_ingest_directory(root=samples_dir, database_url=database_url, queue_commit_chunk_size=1000)
    assert result["enqueued"] == 10
    assert load_pending_queue_count(database_url) == 10
    assert load_photo_count(database_url) == 0


def test_seed_corpus_load_stops_after_queue_submission(monkeypatch):
    calls = []
    monkeypatch.setattr("cli.queue_client.process_pending_queue", lambda *args, **kwargs: calls.append("process"))
    load_seed_corpus_into_queue(...)
    assert calls == []
```

- [ ] **Step 2: Run the queue-boundary tests to verify they fail**

Run: `uv run pytest apps/api/tests/test_ingest.py apps/api/tests/test_seed_corpus_cli.py apps/cli/tests/test_queue_client.py -q`
Expected: FAIL because queue submission is still coupled to API-owned processing behavior.

- [ ] **Step 3: Implement minimal client-side queue submission helpers**

```python
def enqueue_ingest_directory(*, root: Path, database_url: str, queue_commit_chunk_size: int) -> dict[str, int]:
    result = ingest_directory(
        root,
        database_url=database_url,
        trigger_client=NoOpQueueTriggerClient(),
        queue_commit_chunk_size=queue_commit_chunk_size,
    )
    return {"scanned": result.scanned, "enqueued": result.enqueued}
```

- [ ] **Step 4: Run the queue-boundary tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_ingest.py apps/api/tests/test_seed_corpus_cli.py apps/cli/tests/test_queue_client.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/cli/cli/queue_client.py apps/api/app/processing/ingest.py apps/api/app/dev/seed_corpus.py apps/api/tests/test_ingest.py apps/api/tests/test_seed_corpus_cli.py apps/cli/tests/test_queue_client.py
git commit -m "feat(cli): limit client access to ingest queue"
```

### Task 4: Narrow the DB service surface and remove stale route ownership

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/routers/ingest_queue.py`
- Modify: `apps/api/app/dependencies.py`
- Modify: `apps/api/tests/test_main.py`
- Modify: `apps/api/tests/test_ingest_queue_api.py`
- Remove or Modify: `apps/api/app/routers/search.py`
- Remove or Modify: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write the failing DB-service surface tests**

```python
def test_openapi_contains_only_db_service_paths(client):
    schema = client.get("/openapi.json").json()
    assert "/api/v1/internal/ingest-queue/process" in schema["paths"]
    assert "/api/v1/search" not in schema["paths"]


def test_service_health_endpoint_still_exists(client):
    response = client.get("/healthz")
    assert response.status_code == 200
```

- [ ] **Step 2: Run the DB-service tests to verify they fail**

Run: `uv run pytest apps/api/tests/test_main.py apps/api/tests/test_ingest_queue_api.py -q`
Expected: FAIL because the current app still mounts legacy search surfaces and stale API ownership.

- [ ] **Step 3: Implement the minimal DB-service-only router set**

```python
app = FastAPI(title="Photo Organizer DB Service")
app.include_router(ingest_queue_router, prefix="/api/v1")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run the DB-service tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_main.py apps/api/tests/test_ingest_queue_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/main.py apps/api/app/routers/ingest_queue.py apps/api/app/dependencies.py apps/api/tests/test_main.py apps/api/tests/test_ingest_queue_api.py apps/api/app/routers/search.py apps/api/tests/test_search_service.py
git commit -m "refactor(api): narrow service surface to db operations"
```

### Task 5: Align the checked-in OpenAPI contract with the running FastAPI app

**Files:**
- Modify: `apps/api/openapi/spec.yaml`
- Create or Modify: `apps/api/scripts/generate_openapi.py`
- Modify: `apps/api/tests/test_main.py`
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: Write the failing OpenAPI alignment tests**

```python
def test_checked_in_openapi_matches_runtime_schema(client):
    runtime = client.get("/openapi.json").json()
    checked_in = yaml.safe_load(Path("apps/api/openapi/spec.yaml").read_text())
    assert checked_in["paths"] == runtime["paths"]
    assert checked_in["info"]["title"] == runtime["info"]["title"]
```

- [ ] **Step 2: Run the OpenAPI alignment tests to verify they fail**

Run: `uv run pytest apps/api/tests/test_main.py -q`
Expected: FAIL because the checked-in spec still advertises browse/search endpoints that the running service does not expose.

- [ ] **Step 3: Implement the minimal generation or regeneration workflow**

```python
from app.main import app
import yaml

Path("apps/api/openapi/spec.yaml").write_text(
    yaml.safe_dump(app.openapi(), sort_keys=False),
    encoding="utf-8",
)
```

- [ ] **Step 4: Run the OpenAPI tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_main.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/openapi/spec.yaml apps/api/scripts/generate_openapi.py apps/api/tests/test_main.py CONTRIBUTING.md
git commit -m "docs(api): align checked-in openapi with db service"
```

### Task 6: Add container packaging and Compose startup with migration-on-start

**Files:**
- Create: `apps/api/Dockerfile`
- Create: `apps/api/docker/entrypoint.sh`
- Create: `compose.yaml`
- Create: `.env.compose.example`
- Modify: `apps/api/tests/test_migrations.py`
- Create: `apps/api/tests/test_container_entrypoint.py`

- [ ] **Step 1: Write the failing startup and migration tests**

```python
def test_entrypoint_runs_migrations_before_starting_server(monkeypatch):
    calls = []
    monkeypatch.setattr("app.migrations.upgrade_database", lambda url: calls.append(("migrate", url)))
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: calls.append(("serve", kwargs["host"])))
    run_entrypoint(database_url="postgresql://photoorg@db/photoorg")
    assert calls == [("migrate", "postgresql://photoorg@db/photoorg"), ("serve", "0.0.0.0")]


def test_entrypoint_exits_without_serving_when_migration_fails(monkeypatch):
    monkeypatch.setattr("app.migrations.upgrade_database", lambda url: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(SystemExit):
        run_entrypoint(database_url="postgresql://photoorg@db/photoorg")
```

- [ ] **Step 2: Run the startup tests to verify they fail**

Run: `uv run pytest apps/api/tests/test_container_entrypoint.py -q`
Expected: FAIL because the entrypoint and container packaging do not exist.

- [ ] **Step 3: Implement the minimal container entrypoint and Compose baseline**

```sh
python -m app.migrations --database-url "$DATABASE_URL"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
  db-service:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    depends_on:
      postgres:
        condition: service_healthy
```

- [ ] **Step 4: Run the startup tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_container_entrypoint.py apps/api/tests/test_migrations.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/Dockerfile apps/api/docker/entrypoint.sh compose.yaml .env.compose.example apps/api/tests/test_migrations.py apps/api/tests/test_container_entrypoint.py
git commit -m "feat(dev): add compose db-service baseline"
```

### Task 7: Add explicit operator commands and document the Compose workflow

**Files:**
- Modify: `Makefile`
- Modify: `CONTRIBUTING.md`
- Modify: `README.md`
- Create: `apps/e2e/tests/test_compose_smoke.py`

- [ ] **Step 1: Write the failing command-surface tests**

```python
def test_makefile_documents_compose_targets():
    makefile = Path("Makefile").read_text()
    assert "compose-up" in makefile
    assert "compose-migrate" in makefile
    assert "compose-down" in makefile
```

- [ ] **Step 2: Run the command-surface tests to verify they fail**

Run: `uv run pytest apps/e2e/tests/test_compose_smoke.py -q`
Expected: FAIL because the Compose targets and smoke workflow are not documented or implemented.

- [ ] **Step 3: Implement minimal operator targets and docs**

```make
compose-up:
	docker compose up --build -d

compose-migrate:
	docker compose run --rm db-service ./apps/api/docker/entrypoint.sh migrate-only

compose-down:
	docker compose down
```

- [ ] **Step 4: Run the command-surface tests to verify they pass**

Run: `uv run pytest apps/e2e/tests/test_compose_smoke.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Makefile CONTRIBUTING.md README.md apps/e2e/tests/test_compose_smoke.py
git commit -m "docs(dev): document compose startup workflow"
```

### Task 8: Verify the integrated workflow end-to-end

**Files:**
- Modify: `apps/e2e/tests/test_compose_smoke.py`
- Modify: `Makefile`
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: Write the failing integrated smoke test**

```python
def test_compose_stack_and_cli_queue_flow():
    completed = subprocess.run(["make", "compose-smoke"], check=False, text=True, capture_output=True)
    assert completed.returncode == 0
    assert "enqueued=" in completed.stdout
    assert "processed=" in completed.stdout
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run: `uv run pytest apps/e2e/tests/test_compose_smoke.py -q`
Expected: FAIL because the smoke command and integrated workflow do not exist yet.

- [ ] **Step 3: Implement the minimal smoke verification path**

```make
compose-smoke:
	docker compose up --build -d
	./scripts/photo-org ingest apps/api/tests/fixtures/samples --database-url "$$COMPOSE_DATABASE_URL"
	docker compose exec db-service curl -fsS http://localhost:8000/healthz
```

- [ ] **Step 4: Run the integrated verification to confirm it passes**

Run: `uv run pytest apps/e2e/tests/test_compose_smoke.py -q`
Run: `make test`
Run: `make test-e2e`
Expected: PASS, plus a repeatable Compose-backed smoke path for local developers.

- [ ] **Step 5: Commit**

```bash
git add apps/e2e/tests/test_compose_smoke.py Makefile CONTRIBUTING.md
git commit -m "test(dev): add compose-backed smoke verification"
```
