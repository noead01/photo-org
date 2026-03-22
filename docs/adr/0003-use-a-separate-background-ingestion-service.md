# ADR-0003: Use A Separate Background Ingestion Service

- Status: Accepted
- Date: 2026-03-21

## Context

The current API app is shaped around search and UI-facing reads. Continuous folder monitoring, metadata extraction, face detection, and deletion reconciliation are background responsibilities with different performance and failure characteristics.

Running ingestion inline with the request/response API would couple:

- slow filesystem scans
- CPU-heavy media processing
- retryable ingest failures
- user-facing latency

The system also needs run-level stats and operational visibility for ingestion independent of search traffic.

## Decision

Keep the API app focused on serving the UI and administrative endpoints.

Create a separate background worker service responsible for:

- watching configured folders
- scanning and reconciling files
- ingesting metadata and faces
- tracking ingest runs and failures

Expose ingestion state and configuration through the API, but do not make the API service own continuous background ingestion itself.

## Consequences

- the monorepo should gain a worker-oriented app or service
- ingest logic should be implemented in reusable domain modules rather than buried in API endpoints
- the API can expose watched-folder management and ingest stats without directly executing scans
- deployment and operations must account for at least two running services

## Alternatives Considered

- Put ingestion directly inside the API service
- Build only a CLI and run ingestion manually
- Use filesystem event handling inside the UI-facing process
