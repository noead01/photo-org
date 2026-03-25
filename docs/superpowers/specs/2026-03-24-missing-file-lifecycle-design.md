# Missing File Lifecycle Design

Date: 2026-03-24
Issue: #25

## Context

Issue `#25` covers the conservative missing-file lifecycle described by ADR-0007 and the root-health distinction described by ADR-0009.

The shared schema already includes the core file lifecycle fields:

- `photo_files.last_seen_ts`
- `photo_files.missing_ts`
- `photo_files.deleted_ts`
- `photo_files.lifecycle_state`
- `photo_files.absence_reason`
- `photos.deleted_ts`

The current implementation does not use those fields yet.

Today the ingest path:

- scans a directory and enqueues `photo_metadata` payloads
- processes queue rows into `photos`
- treats `photos.path` as the active write target
- does not reconcile absent files over time
- does not update `photo_files`
- does not soft-delete logical photos when all file instances disappear

That leaves the accepted ADRs unimplemented even though the schema can support them.

## Decision

Implement issue `#25` as a reconciliation-focused backend slice centered on `photo_files`.

The implementation should:

- introduce a dedicated reconciliation service that owns file-instance lifecycle transitions
- use a global missing-file grace period in days, default `1`
- mark absent files `missing` on the first healthy reconciliation pass
- advance `missing` files to `deleted` once the grace period has elapsed
- return reappearing files to `active` and clear temporary absence markers
- soft-delete a logical photo only when all of its file instances are `deleted`
- clear `photos.deleted_ts` again if any related file instance becomes non-deleted
- exclude soft-deleted logical photos from default search results

## Approaches Considered

### Recommended: Dedicated Reconciliation Service Around `photo_files`

Add a focused service that receives:

- the watched root identity or root path
- the set of observed file paths from a healthy scan
- the current timestamp
- the global grace-period setting

That service performs file-instance lifecycle updates and then recomputes parent photo deletion state.

Why this is the target:

- keeps lifecycle policy in one place instead of scattering it through queue and search code
- matches the existing schema, which already distinguishes logical photos from file instances
- keeps the current queue-processing slice usable while allowing a later worker scan flow to reuse the same reconciliation logic
- makes later watched-folder availability handling easier because reconciliation already has an explicit service boundary

### Alternative: Extend `upsert_photo()` To Own Missing-File Behavior

This would place reconciliation rules in the existing transitional `photos.path` write flow. It reduces the number of new modules, but it mixes file-instance lifecycle policy into a legacy compatibility path and makes future worker-side scan orchestration harder to reason about.

### Alternative: Derive Photo Deletion Lazily In Read Queries Only

This would avoid some write-time updates, but it pushes core lifecycle semantics into every consumer. The resulting state would be less auditable and harder to inspect operationally, so it is not recommended.

## Design

### Configuration

Use a global configuration value for missing-file deletion grace period:

- environment-backed
- integer number of days
- default `1`
- value `0` means no grace period and allows immediate promotion from `missing` to `deleted` during a healthy reconciliation pass

This issue does not introduce per-folder overrides.

### Reconciliation Boundary

Add a backend reconciliation service dedicated to file lifecycle policy.

Inputs:

- watched folder identifier or watched root path
- observed paths from a healthy scan
- reconciliation timestamp
- grace-period days

Responsibilities:

- upsert or reactivate observed file instances
- mark absent active file instances as `missing`
- advance eligible missing file instances to `deleted`
- reactivate reappearing file instances
- recompute `photos.deleted_ts` for affected parent photos

This service should be reusable from:

- a representative local watched-folder reconciliation path implemented for this issue
- later worker-triggered scan flows

### File-Instance Lifecycle Rules

For a healthy scan of a watched root:

1. Every observed file belonging to the root is treated as currently reachable evidence.
2. If a matching `photo_files` row exists in `active`, `missing`, or `deleted` state, it is updated to:
   - `lifecycle_state = "active"`
   - `last_seen_ts = now`
   - `missing_ts = null`
   - `deleted_ts = null`
   - `absence_reason = null`
3. If no matching `photo_files` row exists, create one in `active` state and associate it with the correct logical photo and watched folder.
4. Any existing `photo_files` row for that watched folder that was not observed during the healthy scan transitions as follows:
   - `active -> missing`
   - set `missing_ts = now` if it was previously null
   - keep `deleted_ts = null`
   - set `absence_reason` to a conservative path-level reason such as `path_removed`
5. A row already in `missing` state becomes `deleted` only when:
   - the watched root is healthy for the current pass
   - the file is still absent
   - either `grace_period_days = 0` or `missing_ts + grace_period_days <= now`
6. When a row becomes `deleted`:
   - set `lifecycle_state = "deleted"`
   - set `deleted_ts = now`
   - preserve the original `missing_ts`

This issue does not need a richer reason taxonomy than the existing `absence_reason` field can support. It should store enough information to distinguish an ordinary missing-path observation from later unreachable-root behavior.

### Logical Photo Soft Delete Rules

Logical photo deletion remains derived from file-instance lifecycle state.

Rules:

- a photo remains active while any related `photo_files` row is not `deleted`
- a photo becomes soft-deleted only when all related `photo_files` rows are `deleted`
- when a photo becomes soft-deleted, set `photos.deleted_ts = now`
- if any related file instance later returns to `active` or `missing`, clear `photos.deleted_ts`

This keeps soft deletion conservative and reversible.

### Search Behavior

Default search results should exclude soft-deleted logical photos by filtering on:

- `photos.deleted_ts IS NULL`

Photos with missing-but-not-deleted file instances should still appear in search.

This issue does not add new admin or UI surfaces for lifecycle visibility.

### Representative Workflow For This Issue

The implementation should prove the lifecycle behavior through a watched-folder reconciliation path that can be exercised locally.

The representative path should:

- accept a watched folder root
- enumerate supported files under that root
- build or refresh the corresponding ingest/domain records for observed files
- call the reconciliation service with the observed set

This can remain a backend or CLI-oriented workflow for now. The issue does not need a finished production worker service as long as the reconciliation behavior is real and repeatable.

### Relationship To Unreachable Storage

ADR-0009 requires the system to distinguish unreachable roots from file deletion. This issue should stay compatible with that direction without attempting to complete the whole watched-folder health feature.

For issue `#25`:

- healthy-scan behavior is in scope
- conservative missing-to-deleted transitions are in scope
- full watched-folder unreachable diagnosis is not in scope

The reconciliation service should therefore be designed so a future caller can suppress missing/deleted advancement when the watched root is not healthy.

## Testing Strategy

Follow TDD during implementation.

### Lifecycle Coverage

Add tests that verify:

- an observed file creates or refreshes an `active` `photo_files` row
- a previously active but absent file becomes `missing`
- a missing file that reappears returns to `active` and clears absence markers
- a zero-day grace period allows immediate `missing -> deleted` advancement during a healthy reconciliation pass
- a missing file does not become `deleted` before the grace period expires
- a missing file becomes `deleted` after the grace period expires on a later healthy reconciliation pass

### Logical Photo Coverage

Add tests that verify:

- a photo is not soft-deleted while any related file instance remains active or missing
- a photo is soft-deleted when all related file instances are deleted
- a soft-deleted photo becomes active again if a related file instance reappears

### Search Coverage

Add tests that verify:

- default search excludes rows where `photos.deleted_ts` is non-null
- photos with only missing file instances remain searchable

### Representative Verification Path

Add an automated test or a repeatable local command that:

- sets up a temporary watched folder
- runs reconciliation with files present
- removes or hides a file
- reruns reconciliation before and after the grace window
- confirms the final file and photo lifecycle state

## Non-Goals

This issue does not attempt to:

- implement the full watched-folder management API
- complete root-unreachable diagnosis and reporting
- add new UI for missing or deleted file visibility
- remove the transitional `photos.path` compatibility field
- redesign ingest queue transport behavior

## Implementation Notes

The implementation should preserve the existing architecture:

- keep route handlers thin
- keep lifecycle policy in a dedicated backend service
- keep persistence details in focused DB modules or repositories
- avoid duplicating lifecycle rules between reconciliation and search

Where the current code still writes transitional compatibility fields on `photos`, those writes may remain for now, but `photo_files` should become the source of truth for missing/deleted lifecycle state.
