# Contributing

## Purpose

This document defines the default development workflow and contribution standards for the monorepo.

This document is intended for contributors and maintainers working on the codebase.

For other audiences:

- see [README.md](README.md) for product overview, installation, and basic usage
- see [DESIGN.md](DESIGN.md) for system architecture and high-level design intent
- see [docs/adr/README.md](docs/adr/README.md) for architectural decision records

## Workflow Standards

### Conventional Commits

Commit messages should follow Conventional Commits.

Examples:

- `feat(api): add watched-folder endpoints`
- `fix(worker): preserve missing state for unreachable roots`
- `docs(adr): add polling decision record`

This supports readable history, consistent changelog generation, and release automation.

### Trunk-Based Development

The preferred workflow is trunk-based development.

Expected characteristics:

- short-lived branches
- frequent integration to the main branch
- avoid long-running divergence
- keep changes small enough to review and validate quickly

### Monorepo Versioning

Versioning should be explicit and automation-friendly across the monorepo.

The project should use semantic versioning principles for releasable artifacts.

Expected direction:

- each packaged component should have an explicit version
- version changes should be automated as part of the release process
- shared conventions should exist so app versions do not drift unpredictably

Whether the monorepo ultimately uses a unified version or per-package versioning should be decided explicitly, but the release process should remain semver-based.

### Pre-Push Validation

Before changes are pushed, the codebase should pass a standard validation pipeline.

That pipeline should include:

- formatting and linting
- static checks where applicable
- unit tests
- coverage threshold validation
- component tests where applicable
- integration tests where applicable

Validation should be fast enough for normal developer use but strict enough to prevent obvious regressions from reaching the main branch.

## Preferred Local Commands

The repo has a workspace-level `pyproject.toml` plus package-level `pyproject.toml` files under `apps/` and `packages/`.
Contributors should prefer the root `Makefile` so the common sync, lint, and test commands run through one documented path.

## Baseline Phase 0 Workflow

Use this as the default contributor path for local Phase 0 work:

1. `make sync`
2. `make migrate` when a local database is needed
3. `make seed-corpus-check`
4. `make seed-corpus-load`
5. `make check`
6. `make test-all` and `make test-e2e` before broader changes or handoff

Environment contracts for that path:

- The repo assumes local Python development through `uv`.
- Generated local artifacts should go under `.local/`.
- The current supported workflow is backend- and API-oriented.
- Compose-based stack startup is not yet the supported baseline contributor workflow.
- The root `Makefile` and `scripts/photo-org` wrapper are the supported command surfaces for this path.

Current high-value targets:

- `make sync`
  - install or refresh the root dev/test environment with `uv`
- `make lint`
  - run the currently enforced Ruff checks for the Phase 0 schema and migration surfaces
- `make test`
  - run the focused schema, migration, and ingest pytest slice
- `make test-all`
  - run the full `apps/api/tests` pytest suite
- `make test-e2e`
  - run the seed-corpus end-to-end pytest slice against the checked-in corpus
- `make check`
  - run `lint` and the focused `test` slice
- `make pre-push`
  - run the local validation path expected before pushing changes
- `make migrate`
  - apply database migrations from the repo root through the wrapper script
- `make env-create`
  - register a local environment with an immutable storage mode and derived local runtime settings
- `make compose-up`
  - build and start the registered Compose runtime for the selected `PHOTO_ORG_ENVIRONMENT`
- `make compose-migrate`
  - rerun database migrations against the registered Compose runtime for the selected `PHOTO_ORG_ENVIRONMENT`
- `make compose-down`
  - stop and remove the selected environment while preserving named volumes
- `make compose-down-volumes`
  - stop and remove the selected environment plus the local Postgres volume
- `make compose-smoke`
  - verify the selected environment by enqueueing work from the host CLI and processing it through the db-service using that environment's immutable storage mode
- `make compose-e2e-smoke`
  - create a random ephemeral environment, run `compose-smoke`, run the checked-in e2e suite against that environment's Compose database, then tear everything back down
- `make seed-corpus-check`
  - validate the checked-in `seed-corpus/` inventory and manifest
- `make seed-corpus-load`
  - migrate and load the checked-in `seed-corpus/` into the local development database
- `uv run python -m app.cli poll-storage-sources --database-url <url>`
  - poll enabled registered storage sources, validate each source marker, and reconcile watched folders through the central polling loop
- `uv run python apps/api/scripts/generate_openapi.py`
  - regenerate the generated OpenAPI YAML artifact at `apps/api/.generated/openapi.yaml` from the current FastAPI app
  - the API also serves the same runtime schema at `GET /openapi.yaml` and the Swagger UI docs at `GET /docs`

OpenAPI contribution notes:

- the runtime FastAPI app is the source of truth for the contract
- `GET /openapi.json` remains the canonical JSON schema emitted by FastAPI
- `GET /openapi.yaml` serves the same schema as YAML for operators and docs consumers
- `GET /docs` serves the Swagger UI docs surface
- `apps/api/.generated/openapi.yaml` is generated locally and is ignored by git; do not commit it

The `pre-push` target is intentionally scoped to checks that are currently expected to pass on this repo state.
As broader lint and type-check coverage is cleaned up, that target should expand rather than drift into a second undocumented workflow.

The default local DB-service workflow is Compose-based and environment-aware.

Public local runtime variables are namespaced with `PHOTO_ORG_` so they do not collide with other systems on the same workstation.
Use `PHOTO_ORG_ENVIRONMENT=<name>` to select a registered local environment, and `make env-create` to create one.
Environment definitions live under `.local/environments/` and are the authoritative local registry for immutable runtime settings, including storage mode.
Optionally provide `PHOTO_ORG_ENV_FILE=/path/to/file.env` to load extra configuration for that environment without changing the registry-backed settings.

Examples:

- `make env-create PHOTO_ORG_ENVIRONMENT=dev PHOTO_ORG_ENV_STORAGE_MODE=persistent`
- `make env-create PHOTO_ORG_ENVIRONMENT=scratch PHOTO_ORG_ENV_STORAGE_MODE=ephemeral`
- `PHOTO_ORG_ENVIRONMENT=dev make compose-up`
- `PHOTO_ORG_ENVIRONMENT=alice make compose-up`
- `PHOTO_ORG_ENVIRONMENT=alice make compose-down`
- `PHOTO_ORG_ENVIRONMENT=alice PHOTO_ORG_ENV_FILE=.env.alice make compose-migrate`

- `PHOTO_ORG_ENVIRONMENT=<name> make compose-up` starts postgres and the db-service container for that environment
- `PHOTO_ORG_ENVIRONMENT=<name> make compose-migrate` reruns schema migration against that environment's Compose-managed database
- `PHOTO_ORG_ENVIRONMENT=<name> make compose-down` stops and removes that environment's local Compose stack while preserving the named Postgres volume for persistent environments
- `PHOTO_ORG_ENVIRONMENT=<name> make compose-down-volumes` stops and removes that environment's local Compose stack and deletes the named Postgres volume for persistent environments
- `PHOTO_ORG_ENVIRONMENT=<name> make compose-smoke` brings the stack up, enqueues the checked-in seed corpus through the host CLI, processes the queue through the db-service endpoint, and tears the stack back down using the environment's registered storage mode
- `make compose-e2e-smoke` creates a random ephemeral environment, runs `compose-smoke`, runs `make test-e2e` with `PHOTO_ORG_E2E_DATABASE_URL` pointed at that environment's Compose database, and removes the environment plus its registry file on exit

At environment creation time, the selected environment derives and records its own Compose project name plus host Postgres and API ports from `PHOTO_ORG_ENVIRONMENT`.
If you need to override those defaults, provide `PHOTO_ORG_POSTGRES_HOST_PORT`, `PHOTO_ORG_API_HOST_PORT`, `PHOTO_ORG_DB_SERVICE_DATABASE_URL`, and `PHOTO_ORG_COMPOSE_DATABASE_URL` when running `make env-create`.

Generated local artifacts should go under `.local/`.

Use that directory for:

- local SQLite databases created for verification or demos
- screenshots, temporary exports, and other generated test outputs
- intermediary local build or workflow state that should not be committed

Contributors should avoid scattering generated files through tracked source directories when a repo-local `.local/` path is sufficient.

### Worker And API Queue Boundary

The current ingest development path uses an API-owned persistence boundary.

Contributors should assume:

- worker-side ingest code queues `photo_metadata` submissions instead of mutating catalog tables directly
- the API service owns processing queued submissions and writing domain tables
- internal queue processing is triggered through the bounded API endpoint rather than ad hoc direct DB writes

Current development implications:

- changes to queue payload shape should stay aligned with the API-side processor contract
- worker-side changes should preserve the queue trigger chunking behavior exposed through `--queue-commit-chunk-size`
- tests for ingest behavior should distinguish queue submission from API-side queue processing

The architectural decision behind this boundary is recorded in ADR-0013.

### Seed Corpus Workflow

The repository now includes a checked-in offline corpus under `seed-corpus/`.

Contributors should assume:

- the corpus exists for end-to-end validation and demos
- every asset in the corpus must be safe to redistribute in-repo
- every asset must record source and license metadata in `seed-corpus/manifest.json`
- the root `Makefile` is the supported command surface for validating and loading the corpus

Current development commands for the corpus are:

- `make seed-corpus-check`
- `make seed-corpus-load`
- `make test-e2e`

The default local seed-corpus load target writes its generated SQLite database under `.local/seed-corpus/`.

Synthetic fixtures remain preferred for unit tests and BDD scenarios. The checked-in corpus is the fixed real-file dataset for the end-to-end workflow.

For missing-file reconciliation verification, run `uv run python -m pytest apps/api/tests/test_ingest.py -q`.
That targeted suite exercises a temporary watched-folder fixture and simulated time so contributors can verify `active`, `missing`, `deleted`, and recovery transitions without bringing up the full worker stack.

For the source-aware central polling loop, register a storage source plus watched folder first, then run `uv run python -m app.cli poll-storage-sources --database-url <url>`.
That command validates the source marker before scanning, surfaces source-aware failures in its exit code and stdout, and reconciles only enabled watched folders attached to registered storage sources.

### Automated Version Updates

Packaging and release workflows should update versions automatically in a controlled way rather than relying on manual edits scattered across the repo.

The automation should:

- follow semantic versioning
- derive version bumps from intentional release inputs
- keep packaged artifacts and metadata aligned

### Release Discipline

The repo should favor repeatable automation over manual release steps.

Over time this should include:

- automated changelog generation from conventional commits
- reproducible package builds
- CI-enforced validation before merge or release
- automated or semi-automated version bumps during packaging
