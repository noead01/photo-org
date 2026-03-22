# ADR-0010: Adopt Layered Architecture And Explicit Component Boundaries

- Status: Accepted
- Date: 2026-03-21

## Context

The project will include:

- a browser-based UI
- an API service
- a background worker for ingestion
- PostgreSQL as the persistence layer

Without explicit architectural boundaries, the codebase will tend to accumulate:

- UI logic coupled to schema details
- route handlers containing business workflows
- duplicated rules across API and worker code
- persistence concerns mixed with domain policy

The system is intended to remain understandable and operable for a long-lived product, so these boundaries should be established early.

## Decision

Adopt a layered architecture with explicit component boundaries.

The core expectations are:

- the UI communicates only with backend APIs
- the UI never accesses the database directly
- the API owns request handling and application-facing contracts
- the worker owns continuous ingestion and reconciliation
- PostgreSQL is the persistence layer and system of record, not an application component in its own right
- business logic should live in backend services and domain modules, not primarily in route handlers or ad hoc SQL

The system should also follow the principles of:

- separation of responsibilities
- loose coupling
- SRP
- DRY
- YAGNI

## Consequences

- backend code should be organized into routes, services/use cases, domain modules, and persistence adapters
- shared backend logic should be reusable by both API and worker paths
- route handlers should stay thin and orchestration-focused
- repositories should focus on persistence concerns rather than policy
- frontend code should depend on API contracts rather than database-aware assumptions

## Alternatives Considered

- Allow the UI to interact directly with the database
- Put substantial business logic directly in FastAPI route handlers
- Let each service duplicate logic independently for speed of implementation
