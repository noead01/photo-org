UV ?= uv
PYTHON := .venv/bin/python
PYTEST := $(PYTHON) -m pytest
RUFF := .venv/bin/ruff
SCHEMA_TESTS := apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_ingest.py
LINT_PATHS := apps/api/alembic apps/api/app/migrations.py apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_ingest.py packages/db-schema/photoorg_db_schema

.PHONY: help sync lint test test-all check pre-push migrate

help:
	@printf '%s\n' \
		'make sync      - install/update the root dev and test environment' \
		'make lint      - run the currently enforced ruff checks for Phase 0 schema/tooling surfaces' \
		'make test      - run the current schema/migration/ingest verification slice' \
		'make test-all  - run the full apps/api pytest suite' \
		'make check     - run lint and the focused test slice' \
		'make pre-push  - run the local validation path expected before push' \
		'make migrate   - apply database migrations through the repo-root wrapper'

sync:
	$(UV) sync --group dev --group test

lint:
	$(RUFF) check $(LINT_PATHS)

test:
	$(PYTEST) $(SCHEMA_TESTS)

test-all:
	$(PYTEST) apps/api/tests

check: lint test

pre-push: check

migrate:
	./scripts/photo-org migrate
