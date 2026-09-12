## Storage Source Incremental Polling Design

Date: 2026-06-07

## Summary

Make `POST /api/v1/internal/storage-sources/poll` fast for large libraries with small daily changes by defaulting the endpoint to incremental polling. Incremental polling should validate sources, walk watched folders, and enqueue only newly discovered or stat-changed files without running full missing-file reconciliation at the end of every pass. Full reconciliation remains available as a slower explicit mode for deletion and move detection.

## Goals

- make routine storage-source polls complete quickly when only a small number of files changed
- preserve source validation, chunked durability, and ingest queue idempotency
- keep additions and modifications discoverable through the existing polling flow
- retain a full reconciliation path for missing and deleted file lifecycle transitions
- keep the implementation aligned with the existing staged-ingest direction where polling stays lightweight

## Non-Goals

- no attempt to make recursive filesystem enumeration itself disappear entirely
- no new per-file concurrency or scheduler redesign
- no change to downstream queue processing semantics
- no attempt to provide immediate deletion detection during incremental polls
- no directory-checkpoint tree or filesystem-specific change-notification mechanism in this iteration

## Problem

The current polling flow still performs full watched-folder truth maintenance on every poll:

- it recursively enumerates every file under each watched folder
- it records observed relative paths for the whole scan
- it finishes by reconciling database state against the full observed path set

For large libraries, this makes routine polling expensive even when only a few files were added. The user’s priority is faster discovery of new photos, and they explicitly accept delayed deletion detection.

## Recommended Approach

Adopt a two-mode polling model:

- `incremental` mode for routine worker polling
- `full` mode for slower reconciliation sweeps

Incremental mode becomes the default for the internal poll endpoint. It should:

1. validate registered storage sources and watched-folder roots as today
2. lazily walk supported photo files under each watched folder
3. process files in durable chunks as today
4. enqueue ingest candidates only when the watched-folder path is new or its stat evidence changed
5. refresh file activity for observed records that already exist
6. mark the watched-folder scan successful when enumeration completes
7. skip end-of-scan missing-file reconciliation

Full mode should preserve current reconciliation semantics:

1. perform the same incremental discovery and chunk processing
2. collect the full observed relative-path set
3. reconcile missing and deleted file lifecycle state after enumeration finishes
4. refresh affected photo deleted timestamps

This keeps the fast path focused on additions and modifications while preserving a correctness path for removals.

## Alternatives Considered

### Directory Timestamp Heuristics

Avoid most work when parent-directory mtimes appear unchanged.

Rejected because it is filesystem-dependent and unreliable for NAS-backed or aliased storage roots. It would also be difficult to reason about correctness across rename and metadata-only changes.

### Persisted Directory Checkpoint Tree

Store directory-level checkpoints and descend only into directories whose metadata changed.

Rejected for now because it adds substantial new state and edge cases around filesystem behavior, renames, and recovery. It is a plausible later optimization if recursive enumeration itself remains too slow after the lighter reconciliation split.

### Keep Full Reconciliation In Every Poll

Retain the current end-of-scan reconciliation behavior and only optimize internal queries.

Rejected because it does not address the accepted product tradeoff. The user explicitly prefers quick discovery of new files over immediate deletion accuracy.

## Architecture

### Polling Mode Contract

`poll_registered_storage_sources()` in [`apps/api/app/processing/ingest_polling.py`](/mnt/d/Projects/photo-org/apps/api/app/processing/ingest_polling.py:1) should accept an explicit reconciliation mode. A small enum-like string contract is sufficient:

- `poll_mode="incremental"`
- `poll_mode="full"`

Using a mode rather than a bare boolean keeps the call sites readable and leaves room for future targeted modes without proliferating flags.

The internal API-owned poll endpoint in [`apps/api/app/routers/ingest_queue.py`](/mnt/d/Projects/photo-org/apps/api/app/routers/ingest_queue.py:1) should default to `incremental`.

### Incremental Poll Flow

Within each watched folder:

- validate the resolved scan root
- iterate files lazily through `iter_photo_files()`
- process chunks through `_process_watched_folder_chunk()`
- accumulate aggregate counts and errors exactly as today
- record chunk-level ingest runs exactly as today

At the end of an incremental scan, polling should not call `reconcile_watched_folder()`. Instead it should perform only lightweight success bookkeeping:

- update watched-folder and storage-source availability through `record_watched_folder_scan_success()`
- refresh any touched photo deleted timestamps only for records explicitly affected during chunk processing, if needed

No file should transition to `missing` or `deleted` during incremental mode solely because it was absent from that scan.

### Full Reconciliation Flow

Full mode reuses the same source validation and chunk-processing path, but it retains the current finalization behavior:

- collect `observed_relative_paths`
- run `reconcile_watched_folder()`
- run `refresh_photo_deleted_timestamps()`
- record watched-folder scan success after reconciliation completes

This ensures existing deletion and move semantics remain available without forcing that cost into every routine poll.

### Implementation Split

Refactor the current finalization helper into two explicit paths:

- lightweight incremental finalization
- full reconciliation finalization

The likely shape is:

- keep `_process_watched_folder_chunk()` as the shared chunk worker
- replace `_finalize_watched_folder_scan()` with a mode-aware finalization helper or two narrowly scoped helpers
- only allocate and populate `observed_relative_paths` when the selected mode requires full reconciliation

This should reduce both database work and in-memory path tracking on the routine path.

### Idempotency And Queue Semantics

Incremental mode must preserve current queue idempotency behavior:

- unchanged files should not create new queue work
- changed files should refresh queue payloads through the existing idempotency key strategy based on watched-folder path and stat evidence
- existing files should continue to refresh file activation metadata when observed

The change is about when reconciliation runs, not about changing candidate identity or downstream extraction semantics.

### Error Handling

Source validation failures and watched-folder scan failures should remain unchanged:

- source validation failures still record one failed ingest run per watched folder with zero files seen
- chunk-level failures still roll back only the failing chunk
- earlier completed chunks remain durable
- watched-folder success is recorded only after the selected finalization path completes successfully

## API Behavior

The internal poll endpoint should continue returning aggregate counts, but its description and docs must clearly state that the default call is an incremental discovery pass rather than a full folder-truth reconciliation.

An explicit request field should allow callers to opt into full reconciliation. A compact request addition is sufficient, for example:

- `poll_mode`, defaulting to `"incremental"`

`drain_queue` and `queue_process_limit` remain unchanged.

## Testing Strategy

Follow focused TDD for the behavior change.

Add or update coverage for:

- incremental polling enqueues newly added files without invoking missing-file reconciliation
- incremental polling leaves absent files unchanged rather than marking them missing or deleted
- repeated incremental rescans remain idempotent for unchanged files
- full polling preserves the current missing and deleted lifecycle transitions
- the internal poll endpoint defaults to incremental mode and forwards explicit full-mode requests correctly

Regression coverage should remain concentrated in:

- `apps/api/tests/test_ingest_polling.py`
- `apps/api/tests/test_ingest.py`
- `apps/api/tests/test_ingest_queue_api.py`

## Verification

Minimum implementation verification:

- `uv run python -m pytest apps/api/tests/test_ingest_polling.py -q`
- `uv run python -m pytest apps/api/tests/test_ingest.py -k "poll_registered_storage_sources" -q`
- `uv run python -m pytest apps/api/tests/test_ingest_queue_api.py -k "poll_storage_sources" -q`

Representative manual validation should also confirm:

- a library with many existing files and a small number of new files completes a routine incremental poll without deletion churn
- a later full poll marks removed paths as missing or deleted according to the configured grace period

## Operational Notes

After this change, operators should treat polling as two cadences:

- frequent incremental polls for discovery
- less frequent full polls for deletion reconciliation

`last_successful_scan_ts` may continue to reflect successful incremental passes, but that timestamp no longer implies that missing-file reconciliation also ran unless the poll was executed in full mode.

## Open Questions Resolved

- Delayed deletion detection is acceptable for the user’s workflow.
- The default internal worker poll should prioritize fast incremental discovery.
- A separate slower full reconciliation path is preferred over filesystem-specific heuristics.
