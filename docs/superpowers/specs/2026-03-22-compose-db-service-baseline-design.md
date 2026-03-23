# Compose DB Service Baseline Design

## Context

Issue `#18` covers the Phase 0 requirement to establish a Docker Compose-based local development stack.

The current repository does not yet provide that baseline cleanly:

- there is no Compose configuration for the local runtime
- `apps/api` currently mixes DB-service behavior, CLI behavior, and legacy API surfaces
- `apps/cli` exists only as a placeholder and does not own the operational commands that should live in a client application
- the checked-in OpenAPI document in [`apps/api/openapi/spec.yaml`](/mnt/d/Projects/photo-org/.worktrees/issue-18-compose-dev-stack/apps/api/openapi/spec.yaml) no longer reflects the FastAPI service accurately

The issue should establish one clear local runtime path without expanding into the future experience service or broader UI stack. The baseline for this slice is the database plus the DB service only.

## Decision

Implement issue `#18` as a local Compose baseline for `postgres + db-service`, while cleaning up the current service boundary to match that runtime.

The initial implementation should:

- add Docker and Compose assets that start PostgreSQL plus the DB service
- keep `apps/api` as the DB service and remove or narrow legacy surfaces that no longer fit that role
- move CLI behavior out of `apps/api` and into `apps/cli`
- allow the CLI to interact directly only with the `ingest_queue` boundary
- keep migrations, queue processing, and domain-table mutations inside the DB service
- update the checked-in OpenAPI description so it matches the actual FastAPI surface that remains after cleanup

This issue intentionally does not include:

- the future experience-facing service for UI requests
- a Compose-managed UI stack
- a generalized background processing platform beyond the current queue-processing slice

## Design

### Service Responsibilities

The local Phase 0 stack should have three distinct runtime roles:

- PostgreSQL as the persistent store and intended long-term local database baseline
- the DB service as the only service that owns domain-table behavior
- the CLI as the developer-operated client for queue submission workflows

The DB service owns:

- database migrations
- queue processing
- domain-table reads and writes
- the FastAPI contract that exposes service-owned operations

The CLI owns:

- local developer command entrypoints
- ingest submission orchestration
- direct queue writes limited to `ingest_queue`
- any queue-scoped status feedback needed for command output

The CLI must not own:

- migrations
- direct domain-table writes
- direct reuse of legacy API-only operational commands that no longer fit the client boundary

### Compose Baseline

Compose should become the documented way to start the local runtime for this slice.

The baseline stack should include:

- a `postgres` service with durable local volume storage
- a `db-service` container configured to connect to that database

The Compose workflow should provide:

- explicit environment wiring for the DB connection
- a predictable local port for the DB service
- a documented startup path contributors can run without ad hoc manual fixes

The CLI should run outside Compose by default in the developer environment, pointed at the Compose-managed stack.

### CLI And Queue Boundary

The current operational commands that still belong to a client should move into `apps/cli`.

For this issue, the allowed direct database interactions from the CLI are restricted to queue behavior:

- enqueue ingest submissions
- inspect queue-related state only if needed for command UX

That preserves the existing architectural intent:

- queue submission is client-owned
- queue interpretation and processing are DB-service-owned
- domain persistence remains behind the DB service boundary

If an existing command in `apps/api` currently performs both queue and domain work, the issue should split that workflow so the CLI performs only the queue-oriented portion and the DB service performs the rest.

### DB Service Cleanup

`apps/api` should be narrowed to a DB service rather than a mixed application host.

This cleanup should include:

- removing or relocating CLI code that belongs in `apps/cli`
- removing stale routes or helpers that no longer represent the DB service boundary
- keeping only the FastAPI surfaces that still correspond to DB-service-owned operations

The checked-in OpenAPI document should be updated as part of this cleanup.

The preferred outcome is:

- either the spec file is generated from the FastAPI app through a documented workflow
- or the checked-in spec remains hand-maintained, but now matches the actual implementation exactly

What should not remain is a stale static contract that advertises endpoints or schemas the service no longer exposes.

### Verification Strategy

Verification should prove both the runtime baseline and the service boundary.

The issue should include:

- automated tests showing CLI queue submission remains limited to `ingest_queue`
- automated tests showing the DB service owns queue processing and domain persistence
- a repeatable Compose-based smoke path that starts the stack and exercises one representative queue-processing flow
- documentation updates that describe Compose as the default local startup path
- updates or fixes to existing tests that currently assume path layouts that break in a worktree, including the fixture lookup failure in [`apps/api/tests/test_ingest.py`](/mnt/d/Projects/photo-org/.worktrees/issue-18-compose-dev-stack/apps/api/tests/test_ingest.py)

## Outcome

After issue `#18`:

- contributors can start the local runtime through Docker Compose
- the repository has a cleaner separation between the CLI client and the DB service
- the CLI is a real app under `apps/cli` rather than a legacy alias into `apps/api`
- the DB service owns migrations, queue processing, and domain-table behavior
- the published OpenAPI description reflects the actual FastAPI surface instead of stale legacy behavior
