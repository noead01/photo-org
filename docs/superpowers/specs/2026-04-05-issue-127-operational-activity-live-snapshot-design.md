# Issue 127 Operational Activity Live Snapshot Design

Date: 2026-04-05
Issue: #127

## Summary

Redesign operational activity around two distinct operator needs:

- `GET /api/v1/operations/activity` shows only activity that is currently underway
- `GET /api/v1/operations/activity/history` shows completed and failed activity for troubleshooting

The live endpoint should answer "what is happening right now?" without mixing in old failures or recovered work. The history endpoint should answer "what happened earlier?" without pretending to be current health.

## Goals

- make the primary activity endpoint a live, poll-friendly snapshot of current work
- separate active work from historical completed and failed work
- split both live and history views into distinct `polling` and `ingest_queue` sections
- expose progress estimates for active work when the backend can support them honestly
- remove the sticky derived global state model from the live endpoint
- preserve enough structured history for operators to understand failure-then-recovery sequences

## Non-Goals

- no per-file event stream in this issue
- no global top-level health state such as `idle` or `attention_required`
- no analytics-oriented aggregation beyond simple live progress summaries
- no UI implementation in this issue

## Current Problem

`GET /api/v1/operations/activity` currently returns a derived summary with top-level states such as `idle`, `polling`, `processing_queue`, and `attention_required`.

That model conflates live work and recent history. A watched-folder poll can fail and later recover, but the endpoint may remain in `attention_required` because an older failure is still present in recent history. This makes the endpoint less trustworthy for operators who are trying to determine whether work is currently active and how far along it is.

The current shape also focuses on coarse state labels rather than the underlying active work. It does not give operators a clear view of which poll or ingest work is underway or what progress has been made so far.

## Recommended Approach

Replace the current summary-only model with two complementary endpoints:

- `GET /api/v1/operations/activity`
  - live snapshot of only active work
  - no historical failures or completed work
- `GET /api/v1/operations/activity/history`
  - paged history of completed and failed work
  - intended for troubleshooting, review, and recovery interpretation

Both endpoints remain split into two top-level sections:

- `polling`
- `ingest_queue`

This keeps operator concerns separate:

- live endpoint: current activity and progress
- history endpoint: completed and failed outcomes over time

## Alternatives Considered

### Single Paged Mixed Journal

Return one newest-first journal interleaving polling and queue events in a single stream.

Rejected because the user wants separate sections, and because a journal-first surface does not directly satisfy the primary operator need of seeing current work and progress at a glance.

### Keep One Endpoint But Mix Live and History

Keep `/operations/activity` as a combined response with active items plus recent completed and failed entries.

Rejected because it recreates the ambiguity that caused the current derived summary to become misleading. Active state and history serve different operator questions and should not share one overloaded payload.

### Per-File Activity Entries

Surface one journal item per file-level ingest action.

Rejected because it would create high-volume noise, obscure the operator view of current progress, and turn the endpoint into an audit feed rather than an operational surface.

## Live Endpoint Design

### Intent

The live endpoint exists to show only currently undergoing work. If nothing is active, nothing should be shown beyond an empty response structure.

It should not describe recovered failures, recent successes, or historical troubleshooting context.

### Response Shape

`GET /api/v1/operations/activity` returns a snapshot with these top-level sections:

- `polling`
- `ingest_queue`

Each section contains:

- `items`: active work entries
- `summary`: aggregate counts and optional progress estimates

No top-level `state`, `signals`, or `recent_failures` fields remain.

### Polling Section

The `polling` section contains active watched-folder polling runs only.

Each item should identify:

- `ingest_run_id`
- `watched_folder_id`
- `storage_source_id`
- `display_name`
- `scan_path`
- `started_ts`
- optional progress fields when available

The section `summary` should include the active run count and aggregate progress fields when those values can be calculated honestly.

### Ingest Queue Section

The `ingest_queue` section contains active ingest queue work only.

Each item should identify:

- `ingest_queue_id`
- `payload_type`
- lightweight object context such as path when already present on the queue row
- `last_attempt_ts`
- optional progress fields when available

The section `summary` should include:

- `pending_count`
- `processing_count`
- optional progress estimate fields

Stalled queue work is still active operator-relevant work and should appear in the live endpoint while it remains unresolved.

### Progress Semantics

Progress must be treated as an estimate, not a promise.

The endpoint should expose progress only where the backend has a defensible basis for it. Otherwise the relevant progress fields should be `null` or absent.

Examples of progress fields that may be supported:

- `files_seen`
- `estimated_files_total`
- `processed_count`
- `estimated_total`
- `percent_complete`

The first implementation does not need to invent new persistence solely to support precise percentages. It may start with partial estimates if they are clearly grounded in existing runtime or persisted data.

## History Endpoint Design

### Intent

The history endpoint exists to show completed and failed operational activity after the fact. It is for troubleshooting and review, not live status polling.

### Response Shape

`GET /api/v1/operations/activity/history` returns separate `polling` and `ingest_queue` sections.

Each section is independently paged and ordered from most recent to oldest.

Each section contains:

- `items`
- `next_cursor`
- `has_more`

### Polling History Entries

Polling history entries should represent watched-folder ingest run outcomes at the run level, not the file level.

Representative entry types:

- `poll_completed`
- `poll_failed`

If active runs are excluded from history, there is no need for a `poll_started` history entry in the initial version.

### Queue History Entries

Queue history entries should represent queue-item outcomes at the queue-row level.

Representative entry types:

- `queue_processing_completed`
- `queue_processing_failed`

If stalled rows are surfaced in history after resolution or timeout classification, they may also use:

- `queue_processing_stalled`

### Recovery Semantics

The history endpoint must make recovery sequences explicit without deriving a global health label.

If a watched-folder poll fails and a later run succeeds, history should simply show:

- the failed polling entry
- the later completed polling entry

Clients can interpret that as recovery without the backend inventing a sticky summary state.

## Data Model and Assembly Strategy

Split the current `operational_activity.py` responsibility into two read models:

- live snapshot assembly
- history journal assembly

The live snapshot should query only rows that correspond to active polling or active queue work. The history journal should query only completed and failed rows.

Existing sources of truth are sufficient for the first version:

- `ingest_runs` for watched-folder polling activity
- `ingest_queue` for queue activity

This design intentionally avoids introducing a new event log table in the first implementation.

## Documentation Changes

Update documentation to reflect the new split:

- `README.md` should describe `/api/v1/operations/activity` as a live snapshot endpoint
- API schema descriptions should distinguish the live endpoint from the history endpoint
- operator guidance should explain that recovery interpretation belongs to history, not the live snapshot

## Testing Strategy

Follow TDD.

Add and update tests for:

- live endpoint returns no active activity when no polling or queue work is underway
- live endpoint returns only active polling items and progress summary fields
- live endpoint returns only active queue items and progress summary fields
- live endpoint does not surface completed or recovered work
- stalled queue work remains visible in the live endpoint while unresolved
- history endpoint returns completed and failed polling entries newest-first
- history endpoint returns completed and failed queue entries newest-first
- history endpoint keeps polling and queue pagination independent
- history endpoint represents failure followed by recovery as separate ordered entries without deriving `attention_required`

Existing tests that assert top-level `state`, `signals`, or `recent_failures` on `/api/v1/operations/activity` should be replaced with tests aligned to the live snapshot contract.

## Verification

Minimum verification for implementation:

- `uv run python -m pytest apps/api/tests/test_operational_activity_api.py -q`
- `uv run python -m pytest apps/api/tests/test_main.py -q`

Representative local validation should also confirm:

- active work appears while polling or queue processing is underway
- no activity is shown once work completes
- history shows failure and later recovery in descending timestamp order

## Open Questions Resolved

- The primary activity endpoint should focus on current live work, not a mixed history journal.
- Polling and ingest queue activity should be shown in separate sections.
- Historical completed and failed activity should move to a separate endpoint.
- File-level events are out of scope for this issue.
- Progress estimates are desirable, but only when the backend can support them honestly.
