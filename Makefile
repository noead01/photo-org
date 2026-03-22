UV ?= uv
PYTHON := .venv/bin/python
PYTEST := $(PYTHON) -m pytest
PYTEST_COV_ARGS := --cov --cov-report=term-missing
RUFF := .venv/bin/ruff
SCHEMA_TESTS := apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_ingest.py
LINT_PATHS := apps/api/alembic apps/api/app/migrations.py apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_ingest.py packages/db-schema/photoorg_db_schema

.PHONY: help sync lint test test-all check pre-push migrate

help:
	@printf '%s\n' \
		'make sync      - install/update the root dev and test environment' \
		'make lint      - run the currently enforced ruff checks for Phase 0 schema/tooling surfaces' \
		'make test      - run the current schema/migration/ingest verification slice' \
		'make test-all  - run the full apps/api pytest suite with the enforced coverage gate' \
		'make check     - run lint and the focused test slice' \
		'make pre-push  - run lint plus the full coverage-enforced test suite' \
		'make migrate   - apply database migrations through the repo-root wrapper'

sync:
	$(UV) sync --group dev --group test

lint:
	$(RUFF) check $(LINT_PATHS)

test:
	$(PYTEST) $(SCHEMA_TESTS)

test-all:
	$(PYTEST) apps/api/tests $(PYTEST_COV_ARGS)

check: lint test

pre-push: lint test-all

migrate:
	./scripts/photo-org migrate
