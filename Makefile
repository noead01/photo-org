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
ifndef PHOTO_ORG_UI_HOST_PORT
PHOTO_ORG_UI_HOST_PORT := $(shell printf '%s' $$((56000 + $(ENVIRONMENT_HASH) % 1000)))
endif
ifndef PHOTO_ORG_DB_SERVICE_DATABASE_URL
PHOTO_ORG_DB_SERVICE_DATABASE_URL := postgresql+psycopg://photoorg:photoorg@postgres:5432/photoorg
endif
ifndef PHOTO_ORG_COMPOSE_DATABASE_URL
PHOTO_ORG_COMPOSE_DATABASE_URL := postgresql+psycopg://photoorg:photoorg@localhost:$(PHOTO_ORG_POSTGRES_HOST_PORT)/photoorg
endif
ifndef PHOTO_ORG_UI_API_BASE_URL
PHOTO_ORG_UI_API_BASE_URL := http://127.0.0.1:$(PHOTO_ORG_API_HOST_PORT)
endif
ifndef PHOTO_ORG_API_CORS_ALLOWED_ORIGINS
PHOTO_ORG_API_CORS_ALLOWED_ORIGINS := http://127.0.0.1:$(PHOTO_ORG_UI_HOST_PORT),http://localhost:$(PHOTO_ORG_UI_HOST_PORT)
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
export PHOTO_ORG_UI_HOST_PORT
export PHOTO_ORG_DB_SERVICE_DATABASE_URL
export PHOTO_ORG_COMPOSE_DATABASE_URL
export PHOTO_ORG_UI_API_BASE_URL
export PHOTO_ORG_API_CORS_ALLOWED_ORIGINS

.PHONY: help sync lint test test-all test-e2e check pre-push migrate env-create compose-up compose-migrate compose-down compose-down-volumes compose-smoke compose-e2e-smoke print-compose-db-url print-compose-api-base-url print-compose-ui-base-url seed-corpus-check seed-corpus-load ensure-environment

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
		'COMPOSE_PROFILES=ui make compose-up PHOTO_ORG_ENVIRONMENT=<name> - include the web UI service' \
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
		"PHOTO_ORG_UI_HOST_PORT := $(PHOTO_ORG_UI_HOST_PORT)" \
		"PHOTO_ORG_DB_SERVICE_DATABASE_URL := $(PHOTO_ORG_DB_SERVICE_DATABASE_URL)" \
		"PHOTO_ORG_COMPOSE_DATABASE_URL := $(PHOTO_ORG_COMPOSE_DATABASE_URL)" \
		"PHOTO_ORG_UI_API_BASE_URL := $(PHOTO_ORG_UI_API_BASE_URL)" \
		"PHOTO_ORG_API_CORS_ALLOWED_ORIGINS := $(PHOTO_ORG_API_CORS_ALLOWED_ORIGINS)" \
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
	until python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$(PHOTO_ORG_API_HOST_PORT)/healthz').read()" >/dev/null 2>&1; do \
		sleep 1; \
	done; \
	./scripts/photo-org seed-corpus validate >/dev/null; \
	$(COMPOSE_STACK) exec -T db-service python -c "from app.processing.ingest import ingest_directory; result = ingest_directory('/photos'); print(f'scanned={result.scanned}'); print(f'enqueued={result.enqueued}')" ; \
	process_json="$$( $(COMPOSE_STACK) exec -T db-service python -c "import json, urllib.request; req = urllib.request.Request('http://localhost:8000/api/v1/internal/ingest-queue/process', data=b'{\"limit\": 1000}', headers={'Content-Type': 'application/json', 'X-Worker-Role': 'ingest-processor'}); print(json.dumps(json.load(urllib.request.urlopen(req))))" )"; \
	python3 -c 'import json, sys; result = json.loads(sys.argv[1]); print("processed=%s" % result["processed"]); print("failed=%s" % result["failed"]); print("retryable_errors=%s" % result["retryable_errors"]); raise SystemExit(1 if result["failed"] or result["retryable_errors"] else 0)' "$$process_json"; \
	face_counts="$$( $(COMPOSE_STACK) exec -T db-service python -c "from sqlalchemy import func, select; from app.db.session import create_db_engine; from app.storage import faces, photos; engine = create_db_engine(); connection = engine.connect(); detected = connection.execute(select(func.count()).select_from(photos).where(photos.c.faces_detected_ts.is_not(None))).scalar_one(); face_rows = connection.execute(select(func.count()).select_from(faces)).scalar_one(); connection.close(); print(f'faces_detected={detected}'); print(f'face_rows={face_rows}'); raise SystemExit(0 if detected > 0 and face_rows > 0 else 1)" )"; \
	printf '%s\n' "$$face_counts"

print-compose-db-url:
	@printf '%s\n' "$(PHOTO_ORG_COMPOSE_DATABASE_URL)"

print-compose-api-base-url:
	@printf '%s\n' "http://127.0.0.1:$(PHOTO_ORG_API_HOST_PORT)"

print-compose-ui-base-url:
	@printf '%s\n' "http://127.0.0.1:$(PHOTO_ORG_UI_HOST_PORT)"

compose-e2e-smoke:
	@set -eu; \
	env_name="smoke-$$(date +%Y%m%d%H%M%S)-$$$$"; \
	env_slug="$$(printf '%s' "$$env_name" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$$//')"; \
	registry_file="$(PHOTO_ORG_ENV_REGISTRY_DIR)/$$env_slug.mk"; \
	cleanup() { \
		cd "$(CURDIR)" && env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_UI_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL -u PHOTO_ORG_UI_API_BASE_URL -u PHOTO_ORG_API_CORS_ALLOWED_ORIGINS -u PHOTO_ORG_PHOTO_LIBRARY_HOST_PATH -u PHOTO_ORG_PHOTO_LIBRARY_CONTAINER_PATH $(MAKE) --no-print-directory compose-down-volumes PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)" >/dev/null 2>&1 || true; \
		rm -f "$$registry_file"; \
	}; \
	trap cleanup EXIT; \
	printf 'smoke_environment=%s\n' "$$env_name"; \
	cd "$(CURDIR)" && env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_UI_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL -u PHOTO_ORG_UI_API_BASE_URL -u PHOTO_ORG_API_CORS_ALLOWED_ORIGINS -u PHOTO_ORG_PHOTO_LIBRARY_HOST_PATH -u PHOTO_ORG_PHOTO_LIBRARY_CONTAINER_PATH $(MAKE) --no-print-directory env-create PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_STORAGE_MODE=ephemeral PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)"; \
	cd "$(CURDIR)" && env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_UI_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL -u PHOTO_ORG_UI_API_BASE_URL -u PHOTO_ORG_API_CORS_ALLOWED_ORIGINS -u PHOTO_ORG_PHOTO_LIBRARY_HOST_PATH -u PHOTO_ORG_PHOTO_LIBRARY_CONTAINER_PATH $(MAKE) --no-print-directory compose-smoke PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)" PHOTO_ORG_COMPOSE_SMOKE_KEEP_RUNNING=1; \
	database_url="$$( cd "$(CURDIR)" && env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_UI_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL -u PHOTO_ORG_UI_API_BASE_URL -u PHOTO_ORG_API_CORS_ALLOWED_ORIGINS -u PHOTO_ORG_PHOTO_LIBRARY_HOST_PATH -u PHOTO_ORG_PHOTO_LIBRARY_CONTAINER_PATH $(MAKE) --no-print-directory -s print-compose-db-url PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)" )"; \
	api_base_url="$$( cd "$(CURDIR)" && env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_UI_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL -u PHOTO_ORG_UI_API_BASE_URL -u PHOTO_ORG_API_CORS_ALLOWED_ORIGINS -u PHOTO_ORG_PHOTO_LIBRARY_HOST_PATH -u PHOTO_ORG_PHOTO_LIBRARY_CONTAINER_PATH $(MAKE) --no-print-directory -s print-compose-api-base-url PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)" )"; \
	cd "$(CURDIR)" && PHOTO_ORG_E2E_DATABASE_URL="$$database_url" PHOTO_ORG_E2E_API_BASE_URL="$$api_base_url" env -u PHOTO_ORG_ENVIRONMENT -u PHOTO_ORG_ENV_STORAGE_MODE -u PHOTO_ORG_ENV_REGISTRY_FILE -u PHOTO_ORG_COMPOSE_PROJECT_NAME -u PHOTO_ORG_POSTGRES_HOST_PORT -u PHOTO_ORG_API_HOST_PORT -u PHOTO_ORG_UI_HOST_PORT -u PHOTO_ORG_DB_SERVICE_DATABASE_URL -u PHOTO_ORG_COMPOSE_DATABASE_URL -u PHOTO_ORG_UI_API_BASE_URL -u PHOTO_ORG_API_CORS_ALLOWED_ORIGINS -u PHOTO_ORG_PHOTO_LIBRARY_HOST_PATH -u PHOTO_ORG_PHOTO_LIBRARY_CONTAINER_PATH $(MAKE) --no-print-directory test-e2e PHOTO_ORG_ENVIRONMENT="$$env_name" PHOTO_ORG_ENV_REGISTRY_DIR="$(PHOTO_ORG_ENV_REGISTRY_DIR)"

seed-corpus-check:
	./scripts/photo-org seed-corpus validate

seed-corpus-load:
	mkdir -p $(dir $(SEED_CORPUS_DB))
	./scripts/photo-org seed-corpus load --database-url $(SEED_CORPUS_DB)
