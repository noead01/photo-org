UV ?= uv
PYTHON := .venv/bin/python
PYTEST := $(PYTHON) -m pytest
PYTEST_COV_ARGS := --cov --cov-report=term-missing
RUFF := .venv/bin/ruff
SCHEMA_TESTS := apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_ingest.py
LINT_PATHS := apps/api/alembic apps/api/app/migrations.py apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_ingest.py packages/db-schema/photoorg_db_schema

.PHONY: help sync lint test test-all test-e2e check pre-push migrate seed-corpus-check seed-corpus-load

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

seed-corpus-check:
	./scripts/photo-org seed-corpus validate

seed-corpus-load:
	./scripts/photo-org seed-corpus load
