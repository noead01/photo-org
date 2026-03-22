# Database Service Boundary Design

## Context

Issue `#17` covers the Phase 0 requirement to define how the API service and the worker interact with persistence after the shared schema work from issue `#16`.

The current code does not reflect the desired service boundary:

- [`apps/api/app/storage.py`](/mnt/d/Projects/photo-org/.worktrees/feature-issue-17-db-service-boundary/apps/api/app/storage.py) still exposes engine and session helpers from the API app
- the ingest path in [`apps/api/app/processing/ingest.py`](/mnt/d/Projects/photo-org/.worktrees/feature-issue-17-db-service-boundary/apps/api/app/processing/ingest.py) opens database connections directly
- no integration mechanism exists for a worker to submit ingest information without also understanding domain persistence details

The intended architecture is narrower than a generic “shared access layer.” The database should be owned and operated by the API service for domain behavior, while the worker should submit ingest information through a queue-like integration path.

This issue is intentionally limited to establishing that boundary and proving one minimal end-to-end path. It should not absorb the full ingestion workflow planned for later Phase 1 issues.

Accepted ADR `0013` defines the architectural direction:

- API-owned domain persistence
- queue-table ingress for worker submissions
- privileged API-triggered processing

## Decision

Implement issue `#17` as an API-owned persistence boundary with a dedicated queue ingress for worker submissions.

The initial implementation should:

- keep domain-table reads and writes inside the API service boundary
- add an internal queue table used only to collect worker-submitted ingest records
- let the worker append queue rows without direct access to domain-table semantics
- add a privileged API endpoint that processes queued rows in bounded batches
- make worker-trigger timing configurable through a queue chunk-size setting

## Design

### Service Responsibilities

The API service owns:

- database engine and session management for domain behavior
- queue-row interpretation
- domain mutation logic
- queue processing authorization

The worker owns:

- observing the filesystem
- producing coarse-grained ingest submission payloads
- appending queue rows
- triggering queue processing through the privileged API endpoint

The queue table owns:

- buffering worker submissions
- tracking processing lifecycle state
- preserving retry and failure evidence

### Queue Table Boundary

The queue table is infrastructure, not product domain state.

Each row should represent a worker-submitted ingest record rather than a direct domain mutation. The payload should contain only the information required for the API to interpret the submission later, along with transport metadata such as:

- queue row identifier
- enqueue timestamp
- worker-supplied idempotency key
- payload type
- payload body
- processing status
- attempt count
- last-attempt timestamp
- last error payload or summary

The queue contract should be append-oriented for the worker. The worker must not need to understand or manipulate catalog tables in order to submit work.

### Processing Flow

Processing should be API-triggered only for Phase 0.

The expected sequence is:

1. the worker discovers ingest information and appends queue rows
2. the worker counts submissions toward a configurable threshold such as `queue_commit_chunk_size`
3. when the threshold is reached, or when the worker performs a final flush, it calls a privileged API endpoint
4. the API claims a bounded batch of queue rows, processes them idempotently, applies domain mutations transactionally, and marks queue rows as completed or failed

Repeated trigger calls must be safe. The worker-side chunk size controls when processing is requested, but the API remains responsible for its own claim size and transaction semantics.

### Authorization Model

Two authorization boundaries are needed:

- database-level rights for the worker should be limited to append-only queue insertion
- API-level rights for queue processing should be limited to a dedicated worker role or equivalent credential

Interactive API clients should not receive queue-processing permissions. Domain-table mutation remains inside the API’s trusted service layer.

### Error Handling And Idempotency

Queue rows should move through a small processing lifecycle such as:

- `pending`
- `processing`
- `completed`
- `failed`

The API processor should record attempts and preserve failure details on the queue rows rather than dropping failed work silently.

Idempotency is required in two places:

- queue submission should support de-duplication through a worker-supplied key or equivalent mechanism
- domain mutation logic must tolerate repeated processing requests safely

### Implementation Scope For Issue #17

Issue `#17` should prove the service boundary with one minimal end-to-end slice.

It should include:

- a queue-table definition in the shared schema package or a clearly owned persistence module
- a queue-oriented write path the worker can call without domain-table knowledge
- an API-owned processor that converts queued records into one minimal domain mutation path
- a privileged API endpoint that triggers bounded processing
- configuration for worker-side queue chunking
- tests and documentation for authorization, idempotency, and the representative processing flow

It should not include:

- the full Phase 1 watched-folder ingestion workflow
- a general-purpose distributed job framework
- background polling or always-on queue consumers inside the API service
- broad refactors of every existing repository or ingest module beyond what is needed to prove the new boundary

## Verification

Verification for issue `#17` should focus on the architectural contract:

- automated tests showing worker submissions can be enqueued without direct domain-table writes
- automated tests for the privileged API processing endpoint and authorization checks
- processor tests that show queue lifecycle transitions and idempotent handling
- one representative end-to-end test from queued worker submission to API-applied domain mutation
- contributor-facing documentation that explains the API, worker, and queue responsibilities clearly

## Outcome

After issue `#17`:

- the repo has an explicit persistence boundary between API-owned domain behavior and worker-submitted ingest records
- downstream ingestion work can build on a queue-to-API contract instead of direct shared domain-table access
- Phase 1 issues can expand ingestion behavior without reopening the core service-boundary decision
