# Core Catalog Schema Design

## Context

Issue `#16` covers the Phase 0 requirement to define the core catalog and labeling schema that downstream API, worker, and deployment work can rely on.

The current implementation in `apps/api/app/storage.py` is an API-local schema that treats `photos.path` as the identity of a photo and does not model the full set of Phase 0 entities. That conflicts with accepted ADRs that require:

- PostgreSQL with `pgvector` as the primary target
- logical `photos` separated from path-specific `photo_files`
- explicit provenance for face labels
- watched-folder and ingest-run entities that support later operational workflows

This issue is intentionally limited to the schema foundation. It should not absorb the broader shared access-layer work planned for issue `#17`.

## Decision

Define the canonical Phase 0 schema in a new shared database package rather than expanding the API-local table definitions in place.

The new package will own the SQLAlchemy metadata and table definitions for:

- `photos`
- `photo_files`
- `faces`
- `people`
- `face_labels`
- `watched_folders`
- `ingest_runs`

The API app may temporarily import these definitions for schema bootstrap, but the package itself is the source of truth.

## Design

### Schema Packaging

Create a new workspace package for shared database schema concerns.

This package will expose:

- shared SQLAlchemy `MetaData`
- PostgreSQL-first column helpers where needed
- table definitions and indexes
- a small schema bootstrap surface used by current tests

The package will not yet own engine/session factories or broad repository code. That remains for issue `#17`.

### Core Tables

#### `photos`

`photos` represents the logical photo, not a specific file path.

Required characteristics:

- UUID primary key
- unique `sha256`
- canonical metadata fields needed by the current system and roadmap
- soft-delete support for later lifecycle work

Representative fields:

- `photo_id`
- `sha256`
- `phash`
- `shot_ts`
- `shot_ts_source`
- `camera_make`
- `camera_model`
- `software`
- `orientation`
- `gps_latitude`
- `gps_longitude`
- `gps_altitude`
- `created_ts`
- `updated_ts`
- `deleted_ts`

#### `photo_files`

`photo_files` represents observed filesystem instances for a logical photo.

Required characteristics:

- UUID primary key
- foreign keys to `photos` and `watched_folders`
- full-path and filename metadata
- file-instance lifecycle and observability fields needed by the missing/unreachable ADRs

Representative fields:

- `photo_file_id`
- `photo_id`
- `watched_folder_id`
- `relative_path`
- `filename`
- `extension`
- `filesize`
- `created_ts`
- `modified_ts`
- `first_seen_ts`
- `last_seen_ts`
- `missing_ts`
- `deleted_ts`
- `lifecycle_state`
- `absence_reason`

#### `faces`

`faces` represents detected face regions belonging to a logical photo.

Required characteristics:

- UUID primary key
- foreign key to `photos`
- bounding-box fields
- optional crop/provenance metadata
- PostgreSQL-first embedding storage with SQLite-compatible fallback for tests

Representative fields:

- `face_id`
- `photo_id`
- `bbox_x`
- `bbox_y`
- `bbox_w`
- `bbox_h`
- `bitmap`
- `embedding`
- `detector_name`
- `detector_version`
- `provenance`
- `created_ts`

#### `people`

`people` stores human-manageable identities used for labeling and later recognition workflows.

Representative fields:

- `person_id`
- `display_name`
- `created_ts`
- `updated_ts`

#### `face_labels`

`face_labels` stores face-to-person assignments with explicit provenance and confidence.

Required characteristics:

- UUID primary key
- foreign keys to `faces` and `people`
- explicit source/provenance support that distinguishes human-confirmed from machine-applied labels

Representative fields:

- `face_label_id`
- `face_id`
- `person_id`
- `label_source`
- `confidence`
- `model_version`
- `provenance`
- `created_ts`
- `updated_ts`

#### `watched_folders`

`watched_folders` represents configured ingest roots.

Required characteristics:

- UUID primary key
- unique root path
- availability and reason fields that support later unreachable-storage behavior

Representative fields:

- `watched_folder_id`
- `root_path`
- `display_name`
- `is_enabled`
- `availability_state`
- `last_failure_reason`
- `last_successful_scan_ts`
- `created_ts`
- `updated_ts`

#### `ingest_runs`

`ingest_runs` provides the minimal audit/history table needed for worker execution tracking.

Representative fields:

- `ingest_run_id`
- `watched_folder_id`
- `status`
- `started_ts`
- `completed_ts`
- `files_seen`
- `files_created`
- `files_updated`
- `files_missing`
- `error_count`
- `error_summary`

### Constraints And Indexes

The schema should include the minimum constraints and indexes that materially protect downstream work:

- unique `photos.sha256`
- unique `watched_folders.root_path`
- foreign keys across all relationships
- indexes for major lookup joins such as `photo_files.photo_id`, `faces.photo_id`, `face_labels.face_id`, and `face_labels.person_id`

Lifecycle and provenance state may be stored as strings in Phase 0 to keep SQLite test compatibility simple. The naming should still reflect the accepted ADR concepts so later migrations can harden them if needed.

### Compatibility Boundary

Issue `#16` should adapt the current schema bootstrap path only as much as needed to make the new package authoritative.

It should not:

- implement the full shared access layer
- migrate all current ingest logic onto the new schema
- add broad Alembic migration workflows

## Verification

Verification for this issue should stay schema-focused:

- automated tests that create the schema on SQLite and assert the expected tables, columns, keys, and core constraints
- targeted checks that PostgreSQL-oriented types still degrade safely for SQLite tests
- updates to existing bootstrap imports so downstream work can consume one canonical schema definition

## Outcome

After this issue:

- the repo has one canonical Phase 0 schema definition
- the schema matches the accepted architecture decisions closely enough for downstream work
- later issues can build shared access, ingestion behavior, and deployment workflows on a stable data model
