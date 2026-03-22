# ADR-0014: Use Lease-Based Queue Claiming For API-Side Ingest Processing

- Status: Proposed
- Date: 2026-03-22

## Context

ADR-0013 established that the worker submits ingest work through a queue table and that the API service owns interpretation of queued payloads and all domain-table mutation.

The current Phase 0 implementation processes queued rows through a bounded internal API endpoint that scans for processable rows, applies domain writes, and marks outcomes.

That shape is acceptable for initial local development, but it leaves open a more specific architectural question:

- how queue processing should behave when multiple trigger requests overlap
- how multiple API service instances could safely participate in processing later
- how interrupted or failed processing attempts should return work to the queue without permanent stranding

These questions matter even before multi-instance deployment becomes an immediate requirement because they constrain:

- queue schema design
- idempotency rules
- retry behavior
- operational visibility

The current queue table already records:

- `status`
- `attempt_count`
- `last_attempt_ts`
- `processed_ts`
- `last_error`

Those fields imply a lease-and-recovery model rather than a permanent lock model, but that expectation should be made explicit.

## Decision

Use lease-based row claiming as the target API-side ingest queue processing model.

The intended processing behavior is:

- a processing run claims one or more processable queue rows
- each claimed row is marked as being processed by updating row state in the queue table
- processing continues in a loop until no processable rows remain for that run
- separate API instances may run the same processing loop concurrently as long as row claiming is safe and exclusive at the row level

Rows should be considered processable when they are:

- `pending`
- `processing` with an expired lease, determined from `last_attempt_ts` and a bounded lease timeout

Rows should not depend on permanent locks that survive crashes.

Instead:

- an in-progress row is protected by its current lease window
- if processing completes successfully, the row is marked `completed`
- if processing fails deterministically, the row is marked `failed`
- if processing fails transiently or a worker crashes mid-attempt, the row remains reclaimable after the lease expires

The internal trigger endpoint should be understood as:

- a request to ensure queue processing is underway
- not a guarantee that exactly one endpoint invocation owns all queue work

For the current single-host Phase 0 implementation, in-process guards may still be used as a local optimization to avoid redundant overlapping scans, but they are not the architectural correctness mechanism.

Correctness should come from database-backed row claiming and lease expiry semantics.

## Consequences

- the queue processor can evolve from a single-instance local implementation toward safe multi-instance participation without changing the worker-to-API boundary
- duplicate processing risk is reduced because row ownership is determined through queue-row state transitions rather than caller timing assumptions
- interrupted processing no longer requires manual cleanup of abandoned locks; stale work becomes reclaimable after lease expiry
- processing code must continue to distinguish retryable failures from terminal failures
- observability becomes more important because operators need to see queue backlog, stale processing rows, retry counts, and failure reasons
- queue-trigger requests become advisory kicks rather than exclusive ownership claims

This decision does not require immediate multi-instance deployment work in Phase 0.

It does require that new queue-processing changes preserve compatibility with lease-based recovery rather than introducing assumptions that only hold for a single active processor.

## Alternatives Considered

- Treat queue processing as single-instance only and reject all overlapping trigger attempts
- Use an external broker before it is operationally justified
- Use permanent row locks without lease expiry or recovery semantics
