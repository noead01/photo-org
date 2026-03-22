# ADR-0001: Use PostgreSQL With pgvector As The Primary Application Database

- Status: Accepted
- Date: 2026-03-21

## Context

The system is expected to store photo metadata, face detections, user labels, ingest state, and face embeddings used for similarity search.

SQLite is convenient for lightweight tests, but it is not the right long-term store for:

- vector embeddings
- vector similarity queries
- richer relational modeling across ingest, photos, files, faces, and labels
- the expected worker-driven operational model

The project already has a PostgreSQL database available with the `vector` extension enabled.

## Decision

Use PostgreSQL as the primary durable application database.

Use `pgvector` for face embeddings and vector similarity search.

SQLite may still be used in narrow local test scenarios, but it is not the target production storage model.

## Consequences

- the primary schema should be designed for PostgreSQL first
- embedding storage should target `vector(128)` or another explicit dimensional vector type
- ingest and API code should share SQLAlchemy models/schema that work against PostgreSQL
- local setup must include a PostgreSQL database with `CREATE EXTENSION vector`

## Alternatives Considered

- Continue with SQLite as the primary store
- Store embeddings outside the relational database
- Use PostgreSQL without `pgvector` and push similarity search elsewhere
