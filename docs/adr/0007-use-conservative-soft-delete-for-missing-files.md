# ADR-0007: Use Conservative Soft-Delete For Missing Files

- Status: Accepted
- Date: 2026-03-21

## Context

The system monitors watched folders that may live on local disks, mounted shared drives, or network-attached storage.

In those environments, a file or whole folder may appear missing temporarily for reasons that do not mean the user actually deleted the photo:

- the shared drive is offline
- the host mount failed
- the worker scanned during a transient network interruption
- a folder tree is being reorganized

If the system immediately hard-deletes or even immediately soft-deletes logical photo records when files disappear from one scan, it will create churn, damage user trust, and make recovery harder.

The system also distinguishes logical photos from file instances, so disappearance of one file path should not imply disappearance of the logical photo if other live file instances remain.

## Decision

Use a conservative missing-to-soft-delete workflow.

For file instances:

- when a previously known file is absent from a scan, mark it as missing rather than deleted
- only mark the file instance as deleted after repeated scans or a configured grace period confirms absence

For logical photos:

- do not soft-delete a logical photo while at least one active file instance remains
- only soft-delete the logical photo when all associated file instances have reached the deleted state

The system should preserve timestamps such as:

- `last_seen_ts`
- `missing_ts`
- `deleted_ts`

## Consequences

- the schema must distinguish active, missing, and deleted file-instance states
- the worker must reconcile absence across time, not just per-scan snapshots
- UI and admin tools should make temporary missing-state visible
- search should exclude soft-deleted logical photos by default
- recovery from transient storage outages becomes safer and more predictable

## Alternatives Considered

- Immediately hard-delete records for missing files
- Immediately soft-delete records after a single missing scan
- Never track missing state separately from deleted state
