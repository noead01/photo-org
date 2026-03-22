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
- `make check`
  - run `lint` and the focused `test` slice
- `make pre-push`
  - run the local validation path expected before pushing changes
- `make migrate`
  - apply database migrations from the repo root through the wrapper script

The `pre-push` target is intentionally scoped to checks that are currently expected to pass on this repo state.
As broader lint and type-check coverage is cleaned up, that target should expand rather than drift into a second undocumented workflow.

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
