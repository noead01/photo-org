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
- `make compose-up`
  - build and start the Compose baseline with postgres plus db-service
- `make compose-migrate`
  - rerun database migrations against the Compose baseline without starting the app server
- `make compose-down`
  - stop and remove the Compose baseline
- `make seed-corpus-check`
  - validate the checked-in `seed-corpus/` inventory and manifest
- `make seed-corpus-load`
  - migrate and load the checked-in `seed-corpus/` into the local development database
- `uv run python apps/api/scripts/generate_openapi.py`
  - regenerate `apps/api/openapi/spec.yaml` from the current FastAPI app

The `pre-push` target is intentionally scoped to checks that are currently expected to pass on this repo state.
As broader lint and type-check coverage is cleaned up, that target should expand rather than drift into a second undocumented workflow.

The default local DB-service workflow is Compose-based:

- `make compose-up` starts postgres and the db-service container
- `make compose-migrate` reruns schema migration against an existing Compose volume
- `make compose-down` stops and removes the local Compose stack

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
