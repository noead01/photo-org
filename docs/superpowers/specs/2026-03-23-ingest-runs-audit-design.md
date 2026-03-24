# Ingest Runs Audit Design

Date: 2026-03-23
Issue: #28

## Context

The Phase 0 schema already includes `ingest_runs`, but the active implementation records operational outcomes primarily on `ingest_queue` rows. That gives queue state, but it does not provide a durable audit trail of processing passes and per-file outcomes over time.

Issue `#28` should make API-side ingest processing produce an explicit audit ledger. The ledger should answer:

- which processing pass ran
- which files were processed in that pass
- whether each file completed, failed permanently, or remained retryable
- what error detail was observed for that file in that pass

## Scope

This design defines ingest runs as API-side queue processing passes, not directory scans.

- `ingest_directory()` remains a scan-and-enqueue step
- `process_pending_ingest_queue()` becomes the run boundary
- unchanged files with the same SHA256 should not create new queue work
- no new queue work means no new processing run

This keeps the audit trail focused on actual domain-processing activity.

## Approaches Considered

### Recommended: Run Header Plus Child Outcome Table

Use `ingest_runs` as the run header and add a new `ingest_run_files` child table for per-file outcomes.

Why this is the target:

- preserves a queryable audit trail instead of burying outcomes in JSON
- keeps transport state (`ingest_queue`) separate from durable audit history
- supports future UI and reporting needs for recent runs, failures, and file-level drill-down
- matches the current ownership boundary where the API service decides final per-file outcomes

### Alternative: Store Per-File Outcomes In `ingest_runs.error_summary` JSON

This minimizes schema changes but makes file-level history difficult to query, sort, and present. It also overloads a run summary field with detailed audit data.

### Alternative: Treat `ingest_queue` As The Audit Log

This reduces new tables but conflates queue transport state with long-lived audit history. Retry and reclaim behavior would make the resulting audit view less clear than a dedicated run ledger.

## Data Model

Keep `ingest_runs` as the run header. Add a new `ingest_run_files` table with one row per queue item processed during a run.

### `ingest_runs`

Retain the existing role of the table:

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

For this issue:

- `files_seen` means queue rows processed in the pass
- `files_created` means `upsert_photo()` inserted a new photo row
- `files_updated` means `upsert_photo()` updated an existing photo row
- `files_missing` remains unused in the current queue-driven path and stays `0`
- `error_count` counts file-level audit rows with non-null error detail
- `error_summary` stores a compact summary of distinct error texts from the run

### New Table: `ingest_run_files`

Add a new table with these columns:

- `ingest_run_file_id` primary key
- `ingest_run_id` foreign key to `ingest_runs.ingest_run_id`
- `ingest_queue_id` foreign key to `ingest_queue.ingest_queue_id`
- `path` text, copied from the payload for direct audit visibility
- `outcome` string enum-like field with values:
  - `completed`
  - `failed`
  - `retryable_error`
- `error_detail` text, nullable
- `created_ts` timestamp with timezone, default current timestamp

Recommended indexes:

- index on `ingest_run_id`
- index on `ingest_queue_id`
- index on `(ingest_run_id, outcome)`

This table records the final disposition seen during one processing pass. It does not attempt to capture every internal state transition.

## Processing Semantics

`process_pending_ingest_queue()` becomes the ingest-run orchestrator.

### Run Creation

When the processor starts:

- call `list_processable(limit=...)`
- if no rows are processable, return the existing empty result and do not create an `ingest_runs` row
- if at least one row is processable, create one `ingest_runs` row with:
  - `status = "processing"`
  - `started_ts = now`

One invocation of `process_pending_ingest_queue()` should produce at most one run row.

### Per-File Outcome Recording

For each queue row successfully claimed in the loop, write exactly one `ingest_run_files` row reflecting the final observed outcome for that run.

Outcome mapping:

- `completed`
  - payload is supported
  - payload parses correctly
  - domain write succeeds
  - face detection warnings do not change the outcome from `completed`
- `failed`
  - unsupported payload type
  - invalid payload content
  - integrity or other deterministic terminal failure
- `retryable_error`
  - transient exception leaves the queue row recoverable after lease expiry

File-level `error_detail` stores the final warning or error text observed in that pass.

### Face Detection Warning Semantics

Face detection remains non-fatal enrichment.

- if photo upsert succeeds and face detection succeeds, record `completed` with no error detail
- if photo upsert succeeds and face detection fails, record `completed` with the warning text in `error_detail`

This preserves the distinction between successful ingest and failed secondary enrichment.

### Run Summary Finalization

When processing ends, update the parent `ingest_runs` row:

- set `completed_ts`
- set `files_seen` to the number of claimed rows that produced an audit record
- set `files_created` from successful inserts
- set `files_updated` from successful updates
- set `error_count` to the number of audit rows with non-null `error_detail`
- set `error_summary` to a compact summary of the first few distinct error texts

Run-level `status` mapping:

- `completed` if every processed file outcome is `completed`
- `failed` if every processed file outcome is `failed`
- `partial` for mixed results, including any run that contains `retryable_error`

## Repeated Folder Scans

The intended behavior for repeated scans of the same folder is:

- if the SHA256 is unchanged, no new queue work should be created
- if no new queue work exists, the API-side processor creates no new run
- if a later scan does create new queue work because content changed, that later processing pass creates a new run and new file audit rows

The audit trail therefore records real processing activity, not redundant scans of unchanged content.

## Testing Strategy

Follow TDD during implementation.

### Schema Coverage

Add tests that verify:

- `ingest_run_files` is exported from the shared schema
- the table is created by metadata and migrations
- `ingest_run_files.ingest_run_id` references `ingest_runs`
- `ingest_run_files.ingest_queue_id` references `ingest_queue`
- expected indexes exist

### Processing Coverage

Add processor tests that verify:

- a processing pass with work creates one `ingest_runs` row
- each processed queue item produces one `ingest_run_files` row
- created vs updated counts are reflected correctly
- permanent failures record `failed` outcomes with error detail
- retryable failures record `retryable_error` outcomes with error detail
- face detection warnings record `completed` outcomes with warning text
- an idle processor call with no processable rows creates no run

## Non-Goals

This issue does not attempt to:

- redefine queue idempotency policy
- model directory scans as ingest runs
- capture every transient internal state transition inside a run
- expose run history through new API endpoints or UI surfaces
- implement missing-file reconciliation in the queue-driven path

## Implementation Notes

The implementation should stay aligned with the current layering:

- keep routes thin
- let the ingest processing service orchestrate run lifecycle
- keep persistence details in dedicated DB modules or repositories
- reuse existing `upsert_photo()` inserted-vs-updated signal for run counters

The audit path should be append-only at the file-outcome level. Queue rows may transition over time, but run-file records should remain stable historical facts once written.
