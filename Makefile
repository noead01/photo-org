UV ?= uv
COMPOSE ?= docker compose
COMPOSE_DATABASE_URL ?= postgresql+psycopg://photoorg:photoorg@localhost:5432/photoorg
PYTHON := .venv/bin/python
PYTEST := $(PYTHON) -m pytest
PYTEST_COV_ARGS := --cov --cov-report=term-missing
RUFF := .venv/bin/ruff
LOCAL_DIR := .local
SEED_CORPUS_DB := $(LOCAL_DIR)/seed-corpus/photoorg.db
SCHEMA_TESTS := apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_ingest.py
LINT_PATHS := apps/api/alembic apps/api/app/migrations.py apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_ingest.py packages/db-schema/photoorg_db_schema

.PHONY: help sync lint test test-all test-e2e check pre-push migrate compose-up compose-migrate compose-down compose-smoke seed-corpus-check seed-corpus-load

help:
	@printf '%s\n' \
		'make sync      - install/update the root dev and test environment' \
		'make lint      - run the currently enforced ruff checks for Phase 0 schema/tooling surfaces' \
		'make test      - run the current schema/migration/ingest verification slice' \
		'make test-all  - run the full apps/api pytest suite with the enforced coverage gate' \
		'make test-e2e  - run the seed-corpus end-to-end verification slice' \
		'make check     - run lint and the focused test slice' \
		'make pre-push  - run lint plus the full coverage-enforced test suite' \
		'make migrate   - apply database migrations through the repo-root wrapper' \
		'make compose-up - build and start the Compose baseline for postgres plus db-service' \
		'make compose-migrate - rerun database migrations against the Compose baseline' \
		'make compose-down - stop and remove the Compose baseline' \
		'make compose-smoke - verify the Compose baseline with host CLI enqueue plus db-service queue processing' \
		'make seed-corpus-check - validate the checked-in seed corpus' \
		'make seed-corpus-load  - migrate and load the checked-in seed corpus'

sync:
	$(UV) sync --group dev --group test

lint:
	$(RUFF) check $(LINT_PATHS)

test:
	$(PYTEST) $(SCHEMA_TESTS)

test-all:
	$(PYTEST) apps/api/tests $(PYTEST_COV_ARGS)

test-e2e:
	PYTHONPATH=apps/api $(PYTEST) apps/e2e/tests -q

check: lint test

pre-push: lint test-all

migrate:
	./scripts/photo-org migrate

compose-up:
	$(COMPOSE) up --build -d

compose-migrate:
	$(COMPOSE) run --rm db-service python -c "from app.migrations import upgrade_database; upgrade_database()"

compose-down:
	$(COMPOSE) down

compose-smoke:
	@set -e; \
	trap '$(COMPOSE) down -v >/dev/null 2>&1 || true' EXIT; \
	$(COMPOSE) up --build -d; \
	until $(COMPOSE) exec -T db-service python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()" >/dev/null 2>&1; do \
		if $(COMPOSE) ps --status exited --services | grep -q '^db-service$$'; then \
			$(COMPOSE) logs db-service; \
			exit 1; \
		fi; \
		sleep 1; \
	done; \
	./scripts/photo-org ingest seed-corpus --database-url "$(COMPOSE_DATABASE_URL)"; \
	processed="$$( $(COMPOSE) exec -T db-service python -c "import json, urllib.request; req = urllib.request.Request('http://localhost:8000/api/v1/internal/ingest-queue/process', data=b'{\"limit\": 1000}', headers={'Content-Type': 'application/json', 'X-Worker-Role': 'ingest-processor'}); print(json.load(urllib.request.urlopen(req))['processed'])" )"; \
	printf 'processed=%s\n' "$$processed"

seed-corpus-check:
	./scripts/photo-org seed-corpus validate

seed-corpus-load:
	mkdir -p $(dir $(SEED_CORPUS_DB))
	./scripts/photo-org seed-corpus load --database-url $(SEED_CORPUS_DB)
