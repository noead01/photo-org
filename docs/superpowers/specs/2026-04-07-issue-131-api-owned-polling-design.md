# Issue 131 API-Owned Polling Design

Date: 2026-04-07
Issue: #131

## Summary

Move storage-source polling fully into the API service and retire the CLI polling command. The API should expose a dedicated internal polling endpoint that performs one bounded poll pass and enqueues ingest candidates only. Queue ingestion remains a separate bounded endpoint that can be invoked concurrently by multiple clients with different `limit` values.

The core design decision is that polling and ingest processing scale differently and therefore should remain separate responsibilities even though they now both live inside the db-service. Polling should reject overlapping scans for the same scope with an explicit HTTP conflict, while ingest queue processing should continue allowing concurrent callers and rely on lease-based row claiming for correctness.

## Goals

- make the db-service the single runtime owner of storage access, polling, extraction, and persistence
- remove the operational need for the `poll-storage-sources` CLI command
- add a dedicated API endpoint that performs polling only and never drains the ingest queue inline
- preserve the existing bounded ingest queue endpoint so multiple clients can process queued work in parallel
- reject overlapping poll requests for the same scope with a dedicated HTTP response and meaningful error payload
- reuse existing ingest-run and operational-activity visibility where practical instead of inventing a second polling-state mechanism

## Non-Goals

- no attempt to merge polling and queue processing into one endpoint
- no redesign of lease-based queue claiming for ingest processing
- no move to an external broker or scheduler for polling kickoff
- no change to watched-folder registration, storage-source identity, or source-marker validation rules beyond what the new endpoint requires
- no broad redesign of developer utilities unrelated to polling ownership

## Current Problem

The current codebase still carries an outdated split:

- the CLI owns `poll-storage-sources`
- the API owns `/api/v1/internal/ingest-queue/process`
- the CLI command also drains the ingest queue after polling finishes

That shape no longer matches the actual deployment reality. The db-service now needs runtime access to photo file contents for staged ingest work such as hashing, metadata extraction, thumbnail generation, and face detection. Keeping polling outside that service no longer creates a clean boundary.

It also creates two practical problems:

- the CLI path violates single-responsibility expectations by polling and then draining the queue in one command
- overlapping poll requests cannot be rejected cleanly at the API boundary because polling does not currently expose a durable in-flight lock or conflict signal

## Recommended Approach

Adopt an API-owned polling model with two independent internal worker endpoints.

### Endpoint 1: Poll Storage Sources

Add an internal endpoint, expected at `POST /api/v1/internal/storage-sources/poll`, with worker-role protection similar to the existing ingest queue endpoint.

Its responsibility is:

- validate the requested poll scope
- reject overlapping poll requests for the same scope
- perform one bounded polling pass
- enqueue ingest candidates
- return aggregate polling counts and errors

It must not:

- process queued ingest work
- loop until the queue is empty
- become a long-running background scheduler separate from the request

### Endpoint 2: Process Ingest Queue

Keep `POST /api/v1/internal/ingest-queue/process` as the ingest-only endpoint.

Its responsibility remains:

- claim processable queue rows
- perform bounded extraction and persistence work
- rely on lease-based queue claiming so multiple callers can overlap safely

This endpoint continues to scale horizontally through concurrent requests and row-level lease semantics. It does not participate in poll overlap control.

## API Contract

### Poll Request

The poll endpoint should accept a compact request body with:

- `poll_chunk_size`, bounded similarly to the current polling function contract
- optional `storage_source_id` to scope the request to one registered source

If `storage_source_id` is omitted, the endpoint polls all enabled registered sources.

Future scope selectors can be added later if operationally justified, but the initial contract should stay minimal.

### Poll Success Response

The response should report polling-only work:

- `scanned`
- `enqueued`
- `inserted`
- `updated`
- `errors`

These fields should preserve the current `IngestResult` semantics so the polling implementation can be reused rather than translated into a different result model.

### Poll Conflict Response

If the requested scope overlaps an active poll, the endpoint should return `409 Conflict` with a specific payload that includes:

- a clear message that polling is already active for the requested scope
- the blocking `storage_source_id`
- the blocking `watched_folder_id` when relevant
- the active `ingest_run_id`
- the active run `started_ts`

This should be precise enough for operators or automation to understand whether the conflict is transient and what work is already underway.

## Scope And Overlap Rules

Overlap should be prevented per watched-folder polling scope, not through a single global poll lock.

The intended behavior is:

- poll-all requests conflict with any active watched-folder poll
- a source-scoped poll request conflicts only with active polls touching watched folders under that source
- different storage sources may be polled independently when their scopes do not overlap

This is stricter than the ingest queue model by design. Filesystem scans should not duplicate work for the same watched folder, while queue row processing is already designed for safe overlap through leases.

## Poll Run Lifecycle

The current polling implementation records completed or failed poll runs after work finishes, but it does not create a durable in-flight marker early enough to reject overlap.

That needs to change.

For each watched-folder scan, polling should:

1. create an ingest run with `status="processing"` before scanning begins
2. keep that run as the active marker for overlap checks and operational activity
3. finalize the run to `completed` or `failed` when the watched-folder poll finishes

Chunk-level progress should continue to be visible through run statistics where useful, but overlap detection must rely on an explicit in-flight run that exists before file enumeration starts.

This design intentionally reuses `ingest_runs` instead of adding a separate poll-lock table unless implementation proves the existing run model cannot express the state cleanly.

## Conflict Detection Source Of Truth

The source of truth for active polling should be `ingest_runs.status == "processing"` for watched-folder-backed runs.

That allows the system to:

- reject overlapping poll requests using state already visible to operational activity
- keep a single operator-facing model for “what is polling right now”
- avoid inventing a second coordination channel just for endpoint conflict handling

If a later implementation needs a more explicit “poll coordinator” abstraction, it should still be backed by this same durable run state rather than in-memory guards alone.

## CLI Changes

Retire the `poll-storage-sources` CLI command from the API app.

The CLI should no longer:

- own storage-source polling
- drain the ingest queue after polling
- present itself as the operator-facing way to run ingestion

Developer utilities such as `migrate` and `seed-corpus` can remain if they still serve local workflows, but polling should move entirely behind the internal API.

## Operational Activity Impact

The existing live activity endpoint already treats `ingest_runs.status == "processing"` as active polling. That aligns well with the new design and should continue to work once polling creates processing runs before scan work begins.

This means:

- the live polling view becomes the same state used for conflict detection
- conflict responses can cite active run identifiers already visible through operations activity
- no separate poll-status endpoint is required for the first version

## Documentation And ADR Direction

Documentation should stop describing polling as a CLI-owned operation and should update the architecture narrative to reflect db-service ownership of file-accessing ingest work.

At minimum:

- contributor docs should replace `poll-storage-sources` instructions with the new internal poll endpoint contract
- README status text should describe polling and queue processing as separate API-owned internal endpoints
- ADR-0003 should be updated or superseded because its original rationale assumed the API service would not need to read photo contents during background ingest work

The revised architectural position is:

- db-service owns polling, hashing, extraction, face detection, and persistence
- separation now exists between polling and ingest-processing responsibilities, not between CLI and API runtimes

## Failure Handling

Failure behavior should remain responsibility-specific.

### Polling Failures

Source validation and watched-folder access failures still belong to the polling path. A failed poll request should return normal polling counts plus error details for the affected sources or folders. It should not attempt compensating queue processing.

### Overlap Failures

Overlap is not an internal error. It is a deliberate API-level conflict and should return `409 Conflict`, not `500`, not silent skipping, and not queue-style lease retry semantics.

### Queue Processing Failures

Queue processing keeps its existing model:

- terminal failures mark rows failed
- transient failures remain retryable
- overlapping processors are acceptable as long as row claiming is exclusive per lease rules

## Testing Strategy

Follow TDD.

Add or update coverage for:

- successful poll endpoint invocation returning polling-only counts
- `409 Conflict` when a poll request overlaps an active poll in the same scope
- source-scoped polls not conflicting with active polls for a different source
- polling creating a `processing` ingest run before scan work starts and finalizing it afterward
- removal of the CLI `poll-storage-sources` command
- docs and OpenAPI coverage for the new endpoint
- existing ingest queue endpoint behavior remaining concurrent and limit-driven

Existing polling tests should be updated where they currently assume only terminal poll runs exist.

## Verification

Minimum verification for implementation:

- targeted API tests for the new polling endpoint, including conflict handling
- targeted polling tests covering the new processing-run lifecycle
- targeted CLI tests confirming `poll-storage-sources` is removed
- targeted ingest queue API tests confirming the current limit-based processing contract still holds

## Open Questions Resolved

- Polling and ingest processing remain separate endpoints to preserve SRP.
- Poll overlap should be rejected with a dedicated HTTP conflict and meaningful payload.
- Queue processing should continue allowing concurrent clients and should scale by saturating the db-service only when needed.
