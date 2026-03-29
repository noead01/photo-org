UV ?= uv
COMPOSE ?= docker compose
LOCAL_DIR := .local
PHOTO_ORG_ENVIRONMENT ?= dev
PHOTO_ORG_ENV_FILE ?=
PHOTO_ORG_ENV_REGISTRY_DIR ?= $(LOCAL_DIR)/environments
ifneq ($(strip $(PHOTO_ORG_ENV_FILE)),)
-include $(PHOTO_ORG_ENV_FILE)
endif

ENVIRONMENT_SLUG := $(shell slug=$$(printf '%s' "$(PHOTO_ORG_ENVIRONMENT)" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$$//'); if [ -n "$$slug" ]; then printf '%s' "$$slug"; else printf 'dev'; fi)
ENVIRONMENT_HASH := $(shell printf '%s' "$(ENVIRONMENT_SLUG)" | cksum | cut -d' ' -f1)
PHOTO_ORG_ENV_REGISTRY_FILE := $(PHOTO_ORG_ENV_REGISTRY_DIR)/$(ENVIRONMENT_SLUG).mk
ifndef PHOTO_ORG_COMPOSE_PROJECT_NAME
PHOTO_ORG_COMPOSE_PROJECT_NAME := photo-org-$(ENVIRONMENT_SLUG)
endif
ifndef PHOTO_ORG_POSTGRES_HOST_PORT
PHOTO_ORG_POSTGRES_HOST_PORT := $(shell printf '%s' $$((54000 + $(ENVIRONMENT_HASH) % 1000)))
endif
ifndef PHOTO_ORG_API_HOST_PORT
PHOTO_ORG_API_HOST_PORT := $(shell printf '%s' $$((55000 + $(ENVIRONMENT_HASH) % 1000)))
endif
ifndef PHOTO_ORG_DB_SERVICE_DATABASE_URL
PHOTO_ORG_DB_SERVICE_DATABASE_URL := postgresql+psycopg://photoorg:photoorg@postgres:5432/photoorg
endif
ifndef PHOTO_ORG_COMPOSE_DATABASE_URL
PHOTO_ORG_COMPOSE_DATABASE_URL := postgresql+psycopg://photoorg:photoorg@localhost:$(PHOTO_ORG_POSTGRES_HOST_PORT)/photoorg
endif
-include $(PHOTO_ORG_ENV_REGISTRY_FILE)
COMPOSE_ENV_FILE_ARG := $(if $(PHOTO_ORG_ENV_FILE),--env-file $(PHOTO_ORG_ENV_FILE),)
COMPOSE_BASE := $(COMPOSE) $(COMPOSE_ENV_FILE_ARG) -p $(PHOTO_ORG_COMPOSE_PROJECT_NAME)
COMPOSE_STACK := $(COMPOSE_BASE) -f compose.yaml $(if $(filter ephemeral,$(PHOTO_ORG_ENV_STORAGE_MODE)),-f compose.ephemeral.yaml)
PYTHON := .venv/bin/python
PYTEST := $(PYTHON) -m pytest
PYTEST_COV_ARGS := --cov --cov-report=term-missing
RUFF := .venv/bin/ruff
SEED_CORPUS_DB := $(LOCAL_DIR)/seed-corpus/photoorg.db
SCHEMA_TESTS := apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_ingest.py
LINT_PATHS := apps/api/alembic apps/api/app/migrations.py apps/api/tests/test_schema_definition.py apps/api/tests/test_migrations.py apps/api/tests/test_ingest.py packages/db-schema/photoorg_db_schema

export PHOTO_ORG_ENVIRONMENT
export PHOTO_ORG_ENV_FILE
export PHOTO_ORG_ENV_REGISTRY_DIR
export PHOTO_ORG_ENV_REGISTRY_FILE
export PHOTO_ORG_ENV_STORAGE_MODE
export PHOTO_ORG_COMPOSE_PROJECT_NAME
export PHOTO_ORG_POSTGRES_HOST_PORT
export PHOTO_ORG_API_HOST_PORT
export PHOTO_ORG_DB_SERVICE_DATABASE_URL
export PHOTO_ORG_COMPOSE_DATABASE_URL

.PHONY: help sync lint test test-all test-e2e check pre-push migrate env-create compose-up compose-migrate compose-down compose-down-volumes compose-smoke compose-e2e-smoke print-compose-db-url seed-corpus-check seed-corpus-load ensure-environment

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
		'make env-create PHOTO_ORG_ENVIRONMENT=<name> PHOTO_ORG_ENV_STORAGE_MODE=<persistent|ephemeral> - register a local environment with immutable storage mode' \
		'make compose-up PHOTO_ORG_ENVIRONMENT=<name> - build and start the selected registered environment' \
		'make compose-migrate PHOTO_ORG_ENVIRONMENT=<name> - rerun database migrations for the selected environment' \
		'make compose-down PHOTO_ORG_ENVIRONMENT=<name> - stop and remove the selected environment while preserving named volumes' \
		'make compose-down-volumes PHOTO_ORG_ENVIRONMENT=<name> - stop and remove the selected environment plus named volumes' \
		'make compose-smoke PHOTO_ORG_ENVIRONMENT=<name> - verify the selected registered environment using its immutable storage mode' \
		'make compose-e2e-smoke - create a random ephemeral environment, run compose smoke plus the checked-in e2e suite, then tear it down' \
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

env-create:
	@case "$(PHOTO_ORG_ENV_STORAGE_MODE)" in \
		persistent|ephemeral) ;; \
		*) printf '%s\n' "PHOTO_ORG_ENV_STORAGE_MODE must be 'persistent' or 'ephemeral'" >&2; exit 1 ;; \
	esac
	@mkdir -p "$(PHOTO_ORG_ENV_REGISTRY_DIR)"
	@candidate="$$(mktemp)"; \
	printf '%s\n' \
		"PHOTO_ORG_ENVIRONMENT := $(PHOTO_ORG_ENVIRONMENT)" \
		"PHOTO_ORG_ENV_STORAGE_MODE := $(PHOTO_ORG_ENV_STORAGE_MODE)" \
		"PHOTO_ORG_COMPOSE_PROJECT_NAME := $(PHOTO_ORG_COMPOSE_PROJECT_NAME)" \
		"PHOTO_ORG_POSTGRES_HOST_PORT := $(PHOTO_ORG_POSTGRES_HOST_PORT)" \
		"PHOTO_ORG_API_HOST_PORT := $(PHOTO_ORG_API_HOST_PORT)" \
		"PHOTO_ORG_DB_SERVICE_DATABASE_URL := $(PHOTO_ORG_DB_SERVICE_DATABASE_URL)" \
		"PHOTO_ORG_COMPOSE_DATABASE_URL := $(PHOTO_ORG_COMPOSE_DATABASE_URL)" \
		> "$$candidate"; \
	if [ -f "$(PHOTO_ORG_ENV_REGISTRY_FILE)" ]; then \
		if cmp -s "$$candidate" "$(PHOTO_ORG_ENV_REGISTRY_FILE)"; then \
			printf '%s\n' "environment already exists: $(PHOTO_ORG_ENVIRONMENT)"; \
			rm -f "$$candidate"; \
		else \
			rm -f "$$candidate"; \
			printf '%s\n' "environment definition is immutable: $(PHOTO_ORG_ENVIRONMENT)" >&2; \
			exit 1; \
		fi; \
	else \
		mv "$$candidate" "$(PHOTO_ORG_ENV_REGISTRY_FILE)"; \
		printf '%s\n' "created environment $(PHOTO_ORG_ENVIRONMENT) at $(PHOTO_ORG_ENV_REGISTRY_FILE)"; \
	fi

ensure-environment:
	@if [ ! -f "$(PHOTO_ORG_ENV_REGISTRY_FILE)" ]; then \
		printf '%s\n' "environment not found: $(PHOTO_ORG_ENVIRONMENT). Run 'make env-create PHOTO_ORG_ENVIRONMENT=$(PHOTO_ORG_ENVIRONMENT) PHOTO_ORG_ENV_STORAGE_MODE=<persistent|ephemeral>' first." >&2; \
		exit 1; \
	fi
	@case "$(PHOTO_ORG_ENV_STORAGE_MODE)" in \
		persistent|ephemeral) ;; \
		*) printf '%s\n' "invalid PHOTO_ORG_ENV_STORAGE_MODE for $(PHOTO_ORG_ENVIRONMENT)" >&2; exit 1 ;; \
	esac

compose-up: ensure-environment
	$(COMPOSE_STACK) up --build -d

compose-migrate: ensure-environment
	$(COMPOSE_STACK) run --rm db-service python -c "from app.migrations import upgrade_database; upgrade_database()"

compose-down: ensure-environment
	$(COMPOSE_STACK) down

compose-down-volumes: ensure-environment
	$(COMPOSE_STACK) down -v

compose-smoke: ensure-environment
	@set -e; \
	cleanup_cmd='$(COMPOSE_STACK) down -v >/dev/null 2>&1 || true'; \
	if [ "$(PHOTO_ORG_COMPOSE_SMOKE_KEEP_RUNNING)" = "1" ]; then \
		cleanup_cmd=':'; \
	fi; \
	trap "$$cleanup_cmd" EXIT; \
	$(COMPOSE_STACK) up --build -d; \
	until $(COMPOSE_STACK) exec -T db-service python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()" >/dev/null 2>&1; do \
		if $(COMPOSE_STACK) ps --status exited --services | grep -q '^db-service$$'; then \
			$(COMPOSE_STACK) logs db-service; \
			exit 1; \
		fi; \
		sleep 1; \
	done; \
	./scripts/photo-org seed-corpus load --database-url "$(PHOTO_ORG_COMPOSE_DATABASE_URL)"; \
	processed="$$( $(COMPOSE_STACK) exec -T db-service python -c "import json, urllib.request; req = urllib.request.Request('http://localhost:8000/api/v1/internal/ingest-queue/process', data=b'{\"limit\": 1000}', headers={'Content-Type': 'application/json', 'X-Worker-Role': 'ingest-processor'}); print(json.load(urllib.request.urlopen(req))['processed'])" )"; \
	printf 'processed=%s\n' "$$processed"

print-compose-db-url:
	@printf '%s\n' "$(PHOTO_ORG_COMPOSE_DATABASE_URL)"

compose-e2e-smoke:
	@set -eu; \
	env_name="smoke-$$(date +%Y%m%d%H%M%S)-$$$$"; \
	env_slug="$$(printf '%s' "$$env_name" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$$//')"; \
	registry_file="$(PHOTO_ORG_ENV_REGISTRY_DIR)/$$env_slug.mk"; \
	cleanup() { \
		env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL $(MAKE) --no-print-directory -C "$(CURDIR)" compose-down-volumes PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)" >/dev/null 2>&1 || true; \
		rm -f "$$registry_file"; \
	}; \
	trap cleanup EXIT; \
	printf 'smoke_environment=%s\n' "$$env_name"; \
	env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL $(MAKE) --no-print-directory -C "$(CURDIR)" env-create PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_STORAGE_MODE=ephemeral PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)"; \
	env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL $(MAKE) --no-print-directory -C "$(CURDIR)" compose-smoke PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)" PHOTO_ORG_COMPOSE_SMOKE_KEEP_RUNNING=1; \
	database_url="$$( env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL $(MAKE) --no-print-directory -C "$(CURDIR)" -s print-compose-db-url PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)" )"; \
	PHOTO_ORG_E2E_DATABASE_URL="$$database_url" env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL $(MAKE) --no-print-directory -C "$(CURDIR)" test-e2e PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)"

seed-corpus-check:
	./scripts/photo-org seed-corpus validate

seed-corpus-load:
	mkdir -p $(dir $(SEED_CORPUS_DB))
	./scripts/photo-org seed-corpus load --database-url $(SEED_CORPUS_DB)
