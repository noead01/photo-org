# Issue 126 Staged Ingest Analysis Design

Date: 2026-04-05
Issue: #126

## Summary

Refactor ingest so watched-folder polling stops performing full media extraction inline. Instead, polling should discover candidate file instances and schedule downstream work, with content hashing and expensive media analysis split into separate stages.

The key design decision is that EXIF extraction, thumbnail generation, and face detection are content-level work, not file-path work. If two file instances have different paths or stat metadata but the same SHA, the system should reuse existing extracted artifacts instead of recomputing them.

## Goals

- keep the sequential polling loop lightweight and operationally responsive
- separate discovery, content identity, expensive analysis, and persistence into distinct responsibilities
- avoid rerunning EXIF extraction, thumbnail generation, and face detection for duplicate-content files
- preserve the existing source-aware watched-folder reconciliation model
- let downstream persistence consume extracted payloads without reopening original files for media analysis
- keep ingest resilient when hashing or extraction fails for individual files

## Non-Goals

- no person recognition or face labeling beyond raw face detection
- no attempt to make one polling process itself highly concurrent while keeping the same mixed responsibilities
- no unrelated schema cleanup beyond what is needed for the staged ingest boundary
- no redesign of watched-folder registration or storage-source validation semantics

## Current Problem

The current ingest path mixes too many responsibilities inside the watched-folder polling flow:

- polling enumerates files
- polling opens original files to derive metadata and thumbnails
- queue processing may reopen original files again to run face detection
- duplicate-content files at different paths may trigger repeated expensive analysis

This has two architectural costs:

- the operator-facing `poll-storage-sources` command remains the throughput bottleneck because it performs expensive work sequentially
- the responsibility boundary between extraction and persistence is unclear, especially for face detection

Recent chunked polling work improved durability and visibility of progress, but it intentionally kept execution serial. Adding more expensive analysis into that same serial loop would make the system slower in practice even if it moved face detection "upstream."

## Recommended Approach

Adopt a staged ingest pipeline with separate boundaries for discovery, content identity, analysis, and persistence.

### Stage 1: Polling And Discovery

Polling should:

- enumerate enabled watched folders under validated storage sources
- identify candidate file instances that may need ingest work
- decide whether a file should advance to hashing based on path and file-state evidence already available at scan time
- record watched-folder progress and reconciliation bookkeeping

Polling should not perform:

- EXIF extraction
- thumbnail generation
- face detection
- other expensive media-derived work that requires the sequential poll loop to read and analyze the whole file

### Stage 2: Hashing And Content Identity

A downstream hashing stage should:

- read candidate files and compute SHA in parallelizable worker execution
- determine whether the content is already known
- decide whether expensive analysis can be skipped because all required derived artifacts already exist for that SHA

This makes SHA the cache boundary for expensive derived artifacts.

### Stage 3: Content Analysis

If the SHA is new, or if required derived artifacts are missing or stale, the system should run content analysis once for that content:

- EXIF extraction
- thumbnail generation
- face detection

This stage should emit a complete extracted payload keyed by content identity rather than path identity.

### Stage 4: Persistence

Persistence should:

- upsert logical photo state using the extracted payload
- persist face detections and derived metadata from the payload
- link or update file instances for the current watched-folder observation
- avoid reopening the original file just to recompute media-derived artifacts

## Why SHA Belongs After Discovery

It is tempting to require the poller to compute SHA before deciding what to do, but that would pull a large fraction of the expensive I/O back into the sequential polling path.

The better split is:

- polling decides which file instances are candidates for further work using path and stat evidence
- hashing computes SHA in a parallelizable stage
- analysis only runs if the SHA is new or artifact-completeness checks fail

This keeps the expensive file-read boundary outside the poller while still using SHA as the reuse key for extracted artifacts.

## Artifact Reuse Rule

The system should treat expensive derived artifacts as content-level assets.

If two observed file instances differ in path or stat metadata but produce the same SHA:

- EXIF extraction should not rerun if the required metadata already exists for that SHA
- thumbnail generation should not rerun if the required thumbnail asset already exists for that SHA
- face detection should not rerun if the required face artifacts already exist for that SHA

Only file-instance linkage and watched-folder reconciliation should update for the new path observation.

This rule is the core reason to split hashing from analysis rather than treating every discovered file as a fresh extraction job.

## Queue And Payload Contracts

The queue contracts should reflect the staged model.

### Discovery-To-Hashing Payload

The discovery stage should enqueue a file-instance candidate payload that contains only the information needed to locate and track the candidate work item. It should not claim that expensive media analysis has already happened.

Expected contents:

- storage source identity and watched-folder identity
- the runtime path needed for a worker to read the file
- the canonical logical path or file-instance path context
- enough stat evidence to support idempotency or stale-work rejection

### Hashing-To-Analysis Decision

After hashing, the system should choose one of two outcomes:

- known content with complete artifacts: skip content analysis and continue to persistence/linkage
- new or incomplete content: enqueue or perform content analysis for that SHA

### Analysis-To-Persistence Payload

The extracted payload should be content-oriented and complete enough that persistence does not need to reopen the original file for media analysis.

Expected contents:

- SHA and content identity
- metadata fields currently derived from extraction
- thumbnail-derived fields and bytes or asset references
- face detections and related warning details
- enough source/file-instance context to link the current observation to the logical photo

## Responsibility Boundaries

The target separation is:

- polling: discovery and watched-folder bookkeeping
- hashing: content identity establishment
- analysis: expensive media-derived artifact generation
- persistence: database mutation from extracted payloads

This is a better single-responsibility split than placing more work into the sequential poller or leaving queue persistence responsible for reopening files.

## Failure Handling

Failure handling should be stage-specific.

### Polling Failures

Source validation and watched-folder reachability failures keep their existing meaning. A folder that cannot be safely scanned should not advance file lifecycle transitions for that scan.

### Hashing Failures

If hashing fails for one candidate file:

- the file should record a retryable or failed work outcome based on the error class
- the watched-folder scan as a whole should not be forced to fail if the broader scan remains valid
- no downstream expensive analysis should run for that candidate

### Analysis Failures

If EXIF extraction, thumbnail generation, or face detection fails:

- the system should preserve the successful hashing and identity result
- the failure should be attached to the work outcome and surfaced in ingest-run visibility
- the design should allow partial success where appropriate, especially if face detection fails but metadata persistence can still proceed

The exact artifact-completeness semantics should be explicit in implementation, but the architecture should support "persist what succeeded, warn about what failed" rather than all-or-nothing media analysis for every file.

## Data Model Direction

The current logical-photo and file-instance split already points in the right direction.

This design strengthens that split:

- file-instance observations belong to watched-folder reconciliation
- expensive derived artifacts belong to content identity keyed by SHA
- persistence should reuse derived artifacts across multiple file instances sharing the same content

Implementation may use existing tables where possible, but the architecture should treat derived artifacts as reusable by content, not owned by a single observed path.

## Testing Strategy

Follow TDD.

Add focused coverage for:

- a polling-driven scan that enqueues candidate work without performing full inline media analysis
- a hashing path that detects known SHA content and skips EXIF and face work
- a new-content path that runs analysis and persists payload-carried face detections
- duplicate-content files at different paths reusing prior extracted artifacts
- queue or worker persistence not reopening original files purely to run face detection
- partial-failure behavior where face detection fails but other ingest data remains persistable

Existing tests that assume polling directly performs the full extraction stack should be updated only where the staged boundary intentionally changes that contract.

## Verification

Minimum verification for implementation:

- `uv run python -m pytest apps/api/tests/test_ingest_polling.py -q`
- `uv run python -m pytest apps/api/tests/test_ingest_queue_processor.py -q`
- `uv run python -m pytest apps/api/tests/test_ingest.py -k "poll_registered_storage_sources or ingest_directory" -q`

Representative local validation should demonstrate:

- a watched folder scan schedules candidate work quickly
- hashing identifies known versus new content
- duplicate-content files skip repeated expensive analysis
- resulting photo detail data includes persisted face regions after the staged pipeline completes

## Alternatives Considered

### Move Face Detection Directly Into The Sequential Poller

Rejected because it technically moves face detection earlier but worsens the operator bottleneck. The poller would remain responsible for too many concerns and would become slower.

### Keep Queue Processing Responsible For Reopening Originals

Rejected because it preserves the current ambiguity in which persistence code also performs media analysis. It also repeats expensive work when extracted payloads should have been reusable.

### Compute SHA Inside The Poller Before Enqueueing

Rejected because SHA computation still requires reading the file. That would move a large part of the expensive work boundary back into the sequential poll path and undercut the point of the split.

## Open Questions Resolved

- The poller should be lightweight and should not become the home of all upstream extraction work.
- SHA is the reuse boundary for expensive derived artifacts.
- Content analysis may be split from hashing so known content can short-circuit downstream work.
- Face detection belongs in the extracted-artifact stage, not in final queue persistence.
