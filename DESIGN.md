# Photo Organizer Design

## Purpose

This document is the high-level design reference for the monorepo.

It describes the intended system shape, major subsystems, core data flows, and the architectural boundaries that should remain stable even as implementation details evolve.

This document is intended for maintainers, architects, and contributors who need to understand how the system is built.

For other audiences:

- see [README.md](README.md) for product overview, installation, and basic usage
- see [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and contribution standards
- see [docs/adr/README.md](docs/adr/README.md) for architectural decision records

Detailed architectural choices and their rationales belong in ADRs under [`docs/adr`](/mnt/d/Projects/photo-org/docs/adr).

## System Goals

The system is intended to:

- ingest photos from one or more user-managed folders
- extract reproducible metadata from the source files
- detect faces and eventually compute embeddings for recognition workflows
- support search, filtering, and inspection in a user-facing UI
- preserve a clear distinction between logical photo identity and filesystem location
- operate locally first, with transparent data and predictable behavior

## Technology Baseline

The default stack for the project is:

### Backend

- Python
- FastAPI for HTTP APIs
- SQLAlchemy for persistence access
- PostgreSQL as the durable system of record
- `pgvector` for face embeddings and similarity search

### Frontend

- React
- browser-based UI consuming backend APIs only

### Background Processing

- Python-based worker service
- polling-based folder reconciliation as the default mechanism

### Operations

- Docker Compose as the default packaging and deployment model
- Redis optional later if justified by concrete queueing or caching needs

## Architectural Principles

The project should follow a small set of explicit engineering principles.

### Separation of Responsibilities

Each major component should have a clear responsibility:

- the UI owns presentation and interaction
- the API owns application-facing contracts and request orchestration
- the worker owns background ingestion and reconciliation
- the database owns persistence only

### No Direct UI-To-Database Access

The UI must never interact with the database directly.

All reads and writes must go through backend APIs or backend-owned processing flows. The frontend should depend on stable API contracts rather than schema internals.

### Component Data Ownership

Each service should own its behavior and interfaces. Shared persistence does not mean shared authority over all logic.

The database is a persistence layer, not the place where application behavior should primarily live.

### Loose Coupling

Components should interact through explicit APIs, jobs, and persisted state rather than by reaching into one another's internal implementation.

This keeps the system easier to test, change, and deploy.

### SRP

Apply the Single Responsibility Principle at multiple levels:

- route handlers should not become business workflows
- repositories should not own domain policy
- worker pipelines should not absorb UI concerns
- modules and classes should have one clear reason to change

### DRY

Avoid duplicating business rules across:

- UI components
- API handlers
- worker jobs
- database-specific code paths

Shared rules should live in reusable backend modules when they are truly shared.

### YAGNI

Do not introduce infrastructure or abstraction before it is justified.

In particular:

- do not require Redis until a real queue or cache need exists
- do not split into extra services prematurely
- do not over-engineer for hypothetical scale before the local-network single-host target is solid

### Explicit Domain Boundaries

The system should preserve explicit domain distinctions, including:

- logical photo identity vs filesystem file instance
- human-confirmed labels vs machine-generated labels
- canonical metadata vs path-derived hints

### Safe Automation

Machine-driven associations and recognition suggestions must be:

- confidence-scored
- provenance-aware
- reversible
- clearly distinguished from human-confirmed truth

### Operational Clarity

The system should favor diagnosable behavior over hidden automation.

Examples:

- distinguish missing files from unreachable storage
- record ingest runs and failures explicitly
- expose ingestion health and recent issues through the system

### Observability And Auditability

The system should make significant actions visible and reviewable over time.

This matters because:

- background ingestion changes the catalog asynchronously
- different users perform different actions with different permissions
- face labeling and correction decisions affect later recognition behavior

The implementation should therefore preserve enough history to answer questions such as:

- what changed
- when it changed
- which user or system actor caused the change
- why the change happened

Examples include:

- ingest runs and their outcomes
- watched-folder configuration changes
- face label creation, correction, and removal
- machine-generated predictions and auto-applied associations
- storage access failures and reconciliation decisions

## Layering Expectations

The backend should be structured so that:

- HTTP routes remain thin
- application services orchestrate use cases
- domain logic stays reusable and testable
- repositories/persistence adapters handle database interaction
- worker processes reuse domain and persistence modules rather than duplicating logic

The database schema supports integrity and queryability, but it should not become the primary home of business rules.

## Audit And Observability Direction

The system should treat observability and auditability as part of the product, not only as internal implementation concerns.

### Audit Expectations

Important user-visible or system-visible actions should be attributable and historically reviewable.

Expected audit dimensions include:

- actor
  - user identity or system component
- action
  - what operation was performed
- target
  - what entity was affected
- timestamp
  - when it happened
- reason or provenance
  - why the system believes it happened

Examples of auditable events:

- watched folder added, removed, enabled, or disabled
- ingest run started, completed, failed, or partially succeeded
- photo file marked missing, deleted, or unreachable
- face label created, changed, confirmed, rejected, or removed
- machine prediction generated or auto-applied

### Observability Expectations

The system should expose enough operational state for users, especially admins, to understand what the system is doing.

That should include:

- current worker and ingest status
- recent run history
- recent failures and warnings
- counts of scanned, inserted, updated, missing, deleted, and failed items
- folder availability and last successful scan information

### Product-Level Requirement

Users should be able to review historical actions performed both by:

- human users
- background system components

This should be reflected in both the data model and the UI/API surface, not only in logs.

## High-Level Architecture

The monorepo should evolve toward a small set of explicit services with clear responsibilities.

### `apps/api`

Primary responsibilities:

- serve the UI and external clients
- expose read/query endpoints for photos, faces, people, search, and stats
- expose admin endpoints for configuration such as watched folders
- avoid doing heavy ingestion work inline with request handling

### `apps/worker` or `apps/ingest`

Primary responsibilities:

- monitor configured folders
- scan for new, changed, moved, and deleted files
- extract metadata
- detect faces
- later compute embeddings and matching candidates
- record ingest runs, file state, and errors

This service should own continuous background ingestion behavior.

### `apps/cli`

Primary responsibilities:

- one-shot operational commands
- local debugging and backfill flows
- maintenance tasks that should reuse the same domain logic as the worker

### `apps/ui`

Primary responsibilities:

- browse and inspect photos
- search and filter
- administer watched folders
- review ingestion status and failures
- label faces and review suggestions

## Core Domain Boundaries

### Logical photo vs file instance

The system should distinguish:

- a logical photo, identified by file content
- a file instance on disk, identified by its observed path within a watched folder

A photo may exist in more than one filesystem location. Moves and renames should not create a new logical photo.

### Search service vs ingest service

The search API should read already-indexed data. The ingest pipeline should mutate the catalog asynchronously. This separation keeps request handling predictable and gives ingestion its own retry/error model.

### Canonical metadata vs derived hints

Canonical metadata comes from the file content itself or deterministic extraction from it, such as:

- content hash
- EXIF data
- file size
- timestamps from the file or embedded metadata

Derived hints come from context, such as:

- folder names
- parent path segments
- import batch names
- watched folder labels

Derived hints are useful for search and faceting, but they should not define photo identity.

## Data Model Direction

The expected long-term model includes at least:

- `photos`
- `photo_files`
- `faces`
- `people`
- `face_labels`
- `watched_folders`
- `ingest_runs`

### `photos`

Represents a logical photo.

Expected characteristics:

- UUID primary key
- unique content hash such as `sha256`
- canonical metadata shared across file instances
- soft-delete semantics driven by file presence across all watched locations

### `photo_files`

Represents an observed file instance.

Expected characteristics:

- one row per filesystem path
- linked to one logical photo
- stores path- and scan-specific state
- used to track renames, moves, missing files, and repeated sightings

### `faces`

Represents detected faces associated with a logical photo.

Expected characteristics:

- bounding box
- optional crop
- provenance
- embedding storage in PostgreSQL with `pgvector`

## Storage Direction

The durable application database should be PostgreSQL with `pgvector`.

Reasons:

- embeddings require vector-native storage and similarity search
- the system needs stronger operational semantics than an embedded database for the long-term model
- the future design includes background workers, ingest runs, and richer relationships

SQLite can still be useful for narrow local tests, but it is not the target production data store.

## Deployment Model

The default target deployment is a single-site installation on a local network.

This project is intended to be straightforward to install and operate for a small group such as a family sharing photos on a shared drive and using a browser-based interface from devices on the same LAN.

### Default Deployment Shape

The preferred deployment model is:

- one always-on host on the local network
- one PostgreSQL instance on that host
- one API service on that host
- one background worker service on that host
- one UI service on that host
- optional Redis only when operationally justified

This should be packaged primarily as a Docker Compose deployment.

### Operational Goals

The default operator experience should be:

1. install Docker on the host
2. configure a small `.env` file
3. start the stack with Docker Compose
4. open the web interface from another device on the LAN
5. add watched folders through the admin UI

The system should avoid requiring shell-level operational knowledge for normal use after initial setup.

### Shared Drive Access

The worker should read photos where they already live rather than requiring users to import or copy them into an application-managed library.

That means the deployment should support:

- host bind mounts for local folders
- mounted shared drives on the host
- a stable internal mount path visible to the worker container

Watched folders should refer to the server-visible path, not arbitrary client-local paths.

### Security Model

The default deployment is local-network only.

Expected defaults:

- local user accounts
- role-based authorization for admin and contributor flows
- no public internet exposure by default
- no dependency on external identity providers

Remote access, TLS termination, and reverse-proxy deployment can be supported later as advanced deployment modes.

### Resilience Expectations

The system should handle common home-network operational failures conservatively:

- if a watched drive is temporarily unavailable, do not immediately soft-delete photo records
- if metadata extraction fails, keep the file in the catalog with partial data
- if face detection fails, keep the photo searchable
- if background services restart, scans and queued work should resume safely

### Backup Expectations

The application should make it clear what needs to be backed up:

- PostgreSQL data
- application configuration
- any external artifact storage if face crops are later stored outside the database

The source photo library itself remains outside the application's ownership.

## Ingestion Flow

The intended ingestion flow is:

1. load watched folder configuration from the database
2. enumerate files in enabled watched folders
3. identify photo candidates by file type
4. hash file content and match or create the logical photo
5. upsert the observed file instance
6. extract metadata
7. detect faces
8. later compute embeddings
9. mark missing file instances and soft-delete logical photos only when no active file instances remain
10. record run-level stats, errors, and timings

## Operational Expectations

The system should provide:

- ingest status visible in the UI
- recent failures and counts visible to users
- admin controls for watched folders
- repeatable one-shot ingest commands for development and backfills

## Relationship To ADRs

Use this file for durable high-level design intent.

Use ADRs for decisions such as:

- service boundaries
- schema direction
- storage choices
- watched-folder behavior
- deletion semantics
- embedding model selection
- event-driven vs polling ingestion

If a design choice has alternatives and rationale, it should be captured as an ADR.
