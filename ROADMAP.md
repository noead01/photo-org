# Roadmap

## Purpose

This document describes the planned feature roadmap for the project and the intended implementation order.

It is not a long-term wishlist. It is a prioritized delivery sequence that should guide incremental implementation.

For architectural rationale, see [DESIGN.md](DESIGN.md) and the ADRs in [docs/adr/README.md](docs/adr/README.md).

## Prioritization Principles

Features should be implemented in an order that:

- produces a user-observable workflow as early as possible
- validates the core product on a small representative corpus
- prefers vertical slices over isolated infrastructure work
- reduces risk in foundational areas before adding convenience features

When choosing between two features:

- prefer the one that improves the end-user workflow on the seed corpus
- defer the one that only prepares for hypothetical scale

## Priority Levels

- `P0`: foundational, blocks the rest of the system
- `P1`: core user value, should follow immediately after foundations
- `P2`: important quality or workflow improvements
- `P3`: useful enhancements that should wait until the core product works well

## Roadmap

### Phase 0: Foundations

Priority: `P0`

Goal:

- establish the architecture, schema direction, deployment model, and seed-corpus workflow needed to build the product safely

Features:

- finalized core schema for `photos`, `photo_files`, `faces`, `people`, `face_labels`, `watched_folders`, and `ingest_runs`
- shared database access layer for API and worker
- seed corpus and repeatable dev load path
- Docker Compose-based local-network deployment baseline
- repo standards and ADR documentation

Definition of done:

- a developer can start the stack locally
- the database model supports the main domain concepts
- the project has one clear development path for the seed corpus

### Phase 1: Corpus Management And Ingestion

Priority: `P0`

Goal:

- make the system able to observe a configured set of folders and keep the catalog synchronized

Features:

- admin-managed watched folders
- worker polling of watched folders
- file reconciliation for new, changed, moved, missing, and deleted files
- EXIF and canonical metadata extraction
- conservative missing and soft-delete lifecycle
- ingest run tracking and error recording
- detection of unreachable storage with root-cause reporting

Definition of done:

- an admin can add a watched folder
- new photos appear in the catalog after background ingestion
- temporary storage outages do not incorrectly delete data
- the system records and exposes ingest failures meaningfully

### Phase 2: Browse And Inspect

Priority: `P1`

Goal:

- let users see what has been ingested and inspect photo details

Features:

- gallery/list view of photos
- photo detail view
- metadata display
- display of detected face regions
- ingestion status visibility in the UI

Definition of done:

- a user can browse the seed corpus
- a user can open a photo and understand its metadata and detected faces
- empty states are clear for photos with no faces or incomplete metadata

### Phase 3: Search And Filtering

Priority: `P1`

Goal:

- make the catalog meaningfully searchable for end users

Features:

- text search
- date range filtering
- person-based filtering
- location filtering and proximity search
- facet-style filters such as has-faces and path-derived hints
- deterministic pagination and stable sorting

Definition of done:

- a user can answer queries such as "photos of Jane from 2005 to 2007 near Paris"
- results feel coherent on the seed corpus
- filter combinations behave predictably

### Phase 4: Face Labeling Workflow

Priority: `P1`

Goal:

- create the user workflow that improves recognition quality over time

Features:

- people management
- face-to-person assignment and correction
- explicit provenance for labels
- distinction between human-confirmed and machine-generated labels
- contributor permissions for validation tasks

Definition of done:

- an authorized user can label or correct faces efficiently
- the system preserves why and how a label was assigned
- the workflow is clearly faster than manual metadata editing outside the app

### Phase 5: Recognition Suggestions

Priority: `P2`

Goal:

- make face recognition useful without sacrificing trust

Features:

- face embeddings stored in PostgreSQL with `pgvector`
- nearest-neighbor candidate lookup
- threshold-based suggestion policy
- auto-apply only above a conservative threshold
- UI review flow for medium-confidence suggestions
- prediction provenance and model version tracking

Definition of done:

- new photos receive useful person suggestions
- users can quickly accept or reject suggested matches
- wrong guesses are easy to correct

### Phase 6: Operational Admin Features

Priority: `P2`

Goal:

- make the system manageable by a non-expert operator on a local network

Features:

- watched-folder health view
- recent ingest errors and run history
- folder enable/disable controls
- manual rescan or backfill triggers
- visibility into catalog size, face counts, unlabeled faces, and pending work

Definition of done:

- an admin can understand whether the system is healthy
- an admin can distinguish configuration issues from temporary storage outages

### Phase 7: Search And Recognition Quality Improvements

Priority: `P3`

Goal:

- improve usefulness after the main workflows are stable

Features:

- ranking refinements using time, location, and co-occurrence hints
- duplicate and near-duplicate handling
- better path-derived metadata labels
- improved recognition evaluation and threshold calibration
- quality dashboards for suggestion performance

Definition of done:

- the product measurably reduces user effort beyond the baseline implementation
- quality improvements are evaluated on the seed corpus before broader scaling

### Phase 8: Packaging And Release Hardening

Priority: `P3`

Goal:

- make installation, upgrades, and releases more predictable

Features:

- complete Compose-based deployment flow
- automated migrations and packaging
- CI validation and release automation
- documented backup and restore workflow

Definition of done:

- a local-network operator can install and upgrade the system with minimal manual steps
- contributors can rely on repeatable validation and release mechanics

## Not Yet Prioritized

These may become roadmap items later, but they should not displace core product delivery until the earlier phases are solid:

- remote access and internet-facing deployment patterns
- advanced queueing or caching infrastructure
- multi-host scaling
- large-scale performance tuning beyond demonstrated need
- richer media experiences such as map and timeline views
