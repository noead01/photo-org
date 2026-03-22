# ADR-0008: Default To Polling For Folder Reconciliation

- Status: Accepted
- Date: 2026-03-21

## Context

The system needs to keep its catalog synchronized with a changing photo corpus in quasi real-time.

Possible approaches include:

- polling watched folders on an interval
- filesystem event watchers such as inotify/FSEvents
- hybrid approaches

The target deployment environment is a single-host local-network installation that may ingest from:

- local disks
- mounted shared drives
- NAS-backed mounts
- container bind mounts

Filesystem event systems are attractive when they work, but they are less reliable across mounted network shares, container boundaries, and heterogeneous operating environments. They also increase implementation complexity and platform-specific behavior.

## Decision

Use polling as the default folder-reconciliation mechanism.

The worker should:

- periodically scan enabled watched folders
- detect additions, changes, missing files, and deletions through reconciliation
- enqueue or perform ingest work asynchronously after the scan

Filesystem event watching may be added later as an optimization, but it should not be the default correctness mechanism.

## Consequences

- the worker implementation is simpler and more portable across deployment environments
- ingestion latency is bounded by scan frequency rather than immediate event delivery
- the system needs efficient scan heuristics to avoid unnecessary rehashing or reprocessing
- quasi real-time behavior should be defined in terms of bounded polling intervals

## Alternatives Considered

- Use filesystem event watchers as the primary mechanism
- Require manual rescans only
- Build a hybrid event-plus-polling system from the start
