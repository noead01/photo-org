# Issue 122 Chunked Polling Design

Date: 2026-04-04
Issue: #122

## Summary

Improve watched-folder polling so large imports make durable progress visible before a full scan completes. Keep execution serial and safe for now: chunk work within a watched-folder scan, commit each chunk durably, and record one `ingest_runs` row per committed chunk.

## Goals

- make durable ingest progress visible during long watched-folder scans
- reduce rollback scope from an entire watched-folder poll to a bounded chunk
- keep the execution model serial within the current safe watched-folder boundary
- preserve correctness for source-aware identity, duplicate-content handling, watched-folder bookkeeping, and repeated scans
- make chunk sizing explicit and configurable

## Non-Goals

- no bounded parallelism in this issue
- no per-file concurrency
- no scheduler or queue-worker changes
- no change to the public meaning of storage-source validation failures

## Current Problem

`poll_registered_storage_sources()` currently validates registered sources, then reconciles each watched folder inside a single transaction per source. Within a watched-folder reconciliation, the implementation enumerates the full file list, processes every file, reconciles missing files, and only then commits and records a single ingest run.

That model has two operational problems for large or NAS-backed folders:

- time to first visible progress is too long because nothing durable appears until the entire scan finishes
- rollback scope is too large because one late failure can discard a long stretch of already-processed work

## Recommended Approach

Keep polling serial across storage sources and watched folders, but replace the monolithic watched-folder transaction with fixed-size file-count chunks.

Within one watched-folder poll:

1. validate the scan root as today
2. enumerate files lazily rather than materializing the entire file list up front
3. process up to `poll_chunk_size` files in one transaction
4. commit photo upserts, thumbnail data, file activation, and one `ingest_runs` row for that chunk
5. continue with the next chunk until enumeration finishes
6. after enumeration is complete, run one final reconciliation phase for missing-file detection using the full observed relative-path set

This keeps the safe execution boundary at a single watched folder while making progress visible incrementally.

## Alternatives Considered

### Time-Based Chunking

Stop and commit when a wall-clock budget expires instead of after a fixed number of files.

Rejected because it is less predictable to tune and harder to test. File-count chunking gives a clearer contract and repeatable behavior.

### Add Parallelism Alongside Chunking

Process multiple watched folders or storage sources concurrently while also chunking.

Rejected for this issue because the user explicitly wants to avoid early throughput optimization. Adding concurrency would complicate correctness analysis before the chunking model is proven.

### Full Enumeration Before Chunked Persistence

Collect the full observed path set first, then process durable chunks.

Rejected because it still delays the first visible durable progress on the large scans this issue is meant to improve.

## Execution Model

### Poll Boundary

`poll_registered_storage_sources()` remains the public entrypoint and remains serial. It still:

- loads enabled watched folders by source
- validates source aliases and markers
- resolves watched-folder roots
- accumulates overall `IngestResult`

No concurrency controls are added in this issue.

### Chunk Boundary

The chunk is the new durability unit for successful watched-folder scanning.

For each chunk:

- open a transaction
- process a bounded number of discovered files
- upsert photo rows and thumbnails
- activate observed file instances
- commit one `ingest_runs` row for that chunk

Chunk counters remain local to that slice:

- `files_seen`
- `files_created`
- `files_updated`
- `error_count`
- `error_summary`

If a chunk processes successfully, its run row is finalized as `completed` even if more chunks remain for the same watched folder.

### Final Reconciliation Phase

Missing-file detection must not run until the full watched-folder enumeration completes. Otherwise a partial scan would incorrectly classify not-yet-seen files as missing.

After the last file chunk commits:

- open a final reconciliation transaction
- compare the full observed relative-path set against existing file instances
- apply missing-file lifecycle transitions
- refresh affected photo deleted timestamps

This phase may produce its own ingest-run record if it needs to surface a durable failure or other explicit bookkeeping outcome, but successful no-op finalization should not create extra synthetic noise beyond the per-file chunks.

## Ingest-Run Semantics

The durable run boundary becomes: one completed chunk, not one entire watched-folder scan.

### Successful Scan Chunks

Each committed file chunk creates one `ingest_runs` row for the watched folder:

- `status = "completed"`
- `files_seen` equals the number of files in the chunk
- `files_created` and `files_updated` describe only that chunk
- `error_count` and `error_summary` describe only errors observed while processing that chunk

This makes progress visible as a sequence of completed runs during a long poll.

### Source Validation Failures

Source validation remains unchanged. If alias or marker validation fails before file processing starts, record one failed run for the watched folder with zero files seen and the existing error summary behavior.

### Failure During Chunk Processing

If a failure happens before a chunk commits, that chunk is rolled back and should record a failed run only for the failed slice. Earlier completed chunks remain durable and visible.

## Configuration

Introduce an explicit polling chunk-size control with a conservative default in application code.

Requirements:

- the chunk size must be configurable from the polling entrypoint
- the default must preserve correctness without assuming aggressive throughput targets
- no worker-count or parallelism setting is introduced in this issue

The CLI may expose this later, but the first implementation only needs the explicit parameter and code default.

## Testing Strategy

Follow TDD.

Add focused coverage for:

- a watched-folder poll large enough to produce multiple completed run rows
- durable photo visibility after the first chunk commits, before the full scan completes
- source validation failures still producing one failed run with zero files seen
- repeated scans remaining correct when earlier chunks already committed
- missing-file reconciliation not firing until the full enumeration finishes

Existing tests that currently assert one successful run for a whole watched-folder scan should be updated only where chunking legitimately changes the contract.

## Verification

Minimum verification for implementation:

- `uv run python -m pytest apps/api/tests/test_ingest_polling.py -q`
- `uv run python -m pytest apps/api/tests/test_ingest.py -k "poll_registered_storage_sources" -q`

Representative local validation should also demonstrate that a large watched-folder poll produces multiple completed run rows before the full scan is finished.

## Open Questions Resolved

- Parallelism is explicitly deferred.
- File-count chunking is preferred over time-budget chunking.
- Each durable chunk becomes its own ingest-run record.
