# Issue 96 Ingest Refactor Design

## Summary

Refactor `apps/api/app/processing/ingest.py` into a thin public facade backed by smaller internal modules for polling orchestration and photo persistence. Preserve the current ingest contract while taking narrow internal cleanup opportunities that improve module boundaries and reduce duplicated policy logic.

## Goals

- Keep `ingest_directory`, `reconcile_directory`, and `poll_registered_storage_sources` stable as the public entrypoints.
- Move watched-folder scan orchestration, registered-source validation, source-relative path handling, and ingest-run recording into a focused polling module.
- Move photo record construction, ingest payload building, and photo upsert behavior into a focused persistence module.
- Reduce duplicated `photos` payload assembly and keep thumbnail retention and source-aware SHA reuse behavior explicit in one place.
- Add direct unit coverage for any new Python module that exposes public functions.

## Non-Goals

- No schema changes for `photos`, `photo_files`, or ingest-run tables.
- No API or CLI contract changes.
- No introduction of a new service-object abstraction layer.
- No broad rewrite of existing ingest tests around internal implementation details.

## Proposed Structure

### Public Facade

`apps/api/app/processing/ingest.py` remains the stable entry surface. It keeps:

- `SUPPORTED_EXTENSIONS`
- `FaceDetector`
- `IngestResult`
- `iter_photo_files`
- `ingest_directory()`
- `reconcile_directory()`
- `poll_registered_storage_sources()`

Its responsibility is limited to input normalization, store/engine setup, and delegation to internal modules.

### Persistence Module

Create `apps/api/app/processing/ingest_persistence.py` for photo-centric logic:

- `PhotoRecord`
- `build_photo_record()`
- `build_ingest_submission()`
- `upsert_photo()`
- `upsert_source_photo()`
- `store_face_detections()`
- supporting hash and timestamp helpers used by those functions

This module becomes the single place for canonical photo identity, metadata extraction, thumbnail preservation, and source-aware hash reuse behavior.

### Polling Module

Create `apps/api/app/processing/ingest_polling.py` for source and watched-folder orchestration:

- `WatchedFolderPollOutcome`
- registered-source target dataclasses
- watched-folder reconciliation flow
- registered-source target loading
- alias and marker validation
- source-relative canonical path building
- source failure classification and description
- ingest-run recording helpers

This module owns the policy-heavy branch logic currently mixed into `ingest.py`.

## Data Flow

### Queue Submission

`ingest_directory()` continues to scan a rooted directory and enqueue queue-only payloads. The facade gathers the file paths and delegates payload construction to `ingest_persistence.build_ingest_submission()`.

### Direct Reconciliation

`reconcile_directory()` continues to:

1. normalize the source root
2. resolve the missing-file grace period
3. ensure the watched folder exists
4. delegate the actual scan/reconciliation flow to the polling module

The polling module drives scan success or failure bookkeeping, photo record creation, upsert behavior, file activation, watched-folder reconciliation, and deleted timestamp refresh.

### Registered Source Polling

`poll_registered_storage_sources()` continues to:

1. load enabled registered-source targets
2. validate aliases and marker files
3. derive scan roots for watched folders
4. reconcile each watched folder
5. record ingest-run outcomes

The facade keeps the top-level loop and result accumulation. The polling module owns target discovery, validation, source-relative canonical path construction, and ingest-run helper behavior.

## Cleanup Scope

Cleanup is allowed only where it improves the new boundaries without changing the ingest contract.

Planned cleanup:

- remove duplicated `photos` payload assembly shared by `upsert_photo()` and `upsert_source_photo()`
- keep thumbnail-retention behavior inside the persistence module rather than the orchestration layer
- keep face-detection timestamp preservation adjacent to source-aware upsert logic
- move registered-source helper dataclasses and functions next to the polling logic that uses them

Not planned:

- renaming public entrypoints
- changing return types
- changing source identity semantics
- changing queue payload shape

## Testing Strategy

Existing behavior remains covered primarily by `apps/api/tests/test_ingest.py`.

Additional direct coverage is required for any new Python module that exposes public functions:

- add `apps/api/tests/test_ingest_persistence.py` for public persistence helpers moved out of the facade
- add `apps/api/tests/test_ingest_polling.py` for public polling helpers moved out of the facade

Testing should stay contract-focused:

- keep facade-level regression coverage in `test_ingest.py`
- add dedicated unit tests only for explicit public module contracts
- avoid asserting on incidental internal decomposition details

## Verification

Minimum verification:

- `uv run python -m pytest apps/api/tests/test_ingest.py -q`
- dedicated unit-test targets for any new public-module test files introduced by the refactor

If the new dedicated unit suites expose gaps in shared helper behavior, expand the focused ingest slice rather than broadening into unrelated suites.
