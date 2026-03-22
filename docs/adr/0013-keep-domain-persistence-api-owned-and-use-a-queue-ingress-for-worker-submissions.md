# ADR-0013: Keep Domain Persistence API-Owned And Use A Queue Ingress For Worker Submissions

- Status: Accepted
- Date: 2026-03-22

## Context

The project architecture already separates the API service from the background worker.

Phase 0 issue `#17` needs to define how those services interact with PostgreSQL without creating long-term coupling between worker code and domain persistence rules.

Two competing pressures exist:

- the worker needs to ingest photos efficiently and may run with multiple threads
- the system should avoid letting multiple services interpret and mutate domain tables independently

If both the API and the worker write directly to catalog tables, the repository will tend to accumulate:

- duplicated persistence logic
- inconsistent transaction boundaries
- schema drift across services
- weaker auditability for domain mutations

At the same time, a purely synchronous REST-only mutation path risks turning interactive API traffic into an ingestion bottleneck.

## Decision

Adopt an API-owned domain persistence model with an internal queue ingress for worker submissions.

The core expectations are:

- the API service is the only component that reads or writes domain tables as part of application behavior
- the worker does not mutate domain tables directly
- the worker may append records to a dedicated queue table that exists only as an integration mechanism
- the queue table is not part of the user-facing product domain model
- the worker may call a privileged API endpoint to request processing of queued records
- the API interprets queued records, applies domain mutations, and records queue outcomes

The worker-side trigger behavior should be operationally configurable, for example through a `queue_commit_chunk_size` setting that controls when the worker asks the API to process queued records.

## Consequences

- domain invariants, idempotency rules, and audit semantics stay concentrated in the API service
- the worker only needs to understand the queue write contract, not the catalog schema
- ingestion can batch submissions without requiring a high-volume synchronous mutation API
- the system needs explicit queue-record lifecycle fields such as status, attempts, and error details
- the worker needs tightly scoped credentials:
  - append-only access to the queue table
  - a dedicated API role for the privileged processing endpoint
- repeated processing triggers must be safe, which requires idempotent API-side processing
- PostgreSQL now serves both as the system of record and as the local queue transport for this phase

## Alternatives Considered

- Let the worker write domain tables directly
- Route all worker mutations through synchronous REST endpoints
- Introduce an external queue or broker in Phase 0
