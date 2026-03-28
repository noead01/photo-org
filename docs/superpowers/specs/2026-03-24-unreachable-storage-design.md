# Unreachable Storage Design

Date: 2026-03-24
Issue: #26

## Context

Issue `#26` extends the missing-file lifecycle work by implementing the heuristic from ADR-0009:

- storage or volume-level access failures should be treated as unreachable storage, not deletion evidence
- path-level absence should only advance toward `missing` or `deleted` when the watched root is otherwise accessible

The current backend already supports:

- `watched_folders.availability_state`
- `watched_folders.last_failure_reason`
- `watched_folders.last_successful_scan_ts`
- `photo_files` lifecycle transitions for healthy scans

What is missing is the scan-time distinction between:

- a healthy traversal where some files are absent
- a failed traversal where the watched root cannot be accessed reliably at all

Without that distinction, a temporary mount, network, permission, or I/O failure could be mistaken for user-driven deletion.

## Decision

Implement the first slice of unreachable-storage handling at the scan boundary in `reconcile_directory()`.

The scan path should:

- classify root-level traversal failures before running missing-file reconciliation
- mark the watched folder unreachable when the root cannot be scanned
- skip file lifecycle advancement on unreachable scans
- preserve the existing healthy-scan behavior for path-level absence

This follows the current heuristic:

- if the access error is due to a volume or network access problem, treat the watched root as unreachable
- if other files or folders on the same volume are accessible, treat a specific file absence as deletion evidence and run the normal missing/deleted lifecycle

## Approaches Considered

### Recommended: Root Health Classification In The Scan Entry Point

Add a small scanning helper used by `reconcile_directory()` that attempts to enumerate supported files and returns either:

- a successful set of observed files for a healthy scan
- a classified root failure for an unreachable scan

Why this is the target:

- the ingest boundary is where filesystem exceptions are actually visible
- it keeps root-health diagnosis out of the file lifecycle service, which should remain focused on policy after scan health is known
- it preserves the existing reconciliation service with minimal surface-area change
- it directly implements the accepted heuristic without inventing a broader health model

### Alternative: Pass A Health Flag Into File Reconciliation

This would make the lifecycle service explicitly root-health aware, but the current caller is the only layer that sees traversal exceptions. Adding the classification later in the call chain would increase indirection without improving the decision quality for this slice.

### Alternative: Infer Unreachability From Failed Runs Only

This would update ingest-run reporting but would not reliably protect file lifecycle state in the same execution path. The core issue is behavioral, not just observational, so this is not sufficient.

## Design

### Scan Classification

Introduce a scan helper that walks the watched root and distinguishes:

- healthy scan
- unreachable scan

Healthy scan means:

- the root can be traversed
- supported files can be enumerated
- file-specific absence is meaningful evidence

Unreachable scan means traversal fails at the root or volume level due to errors such as:

- `FileNotFoundError`
- `PermissionError`
- `OSError`

This first slice does not need a perfect taxonomy. It only needs to classify errors coarsely enough to avoid treating root-access failure as deletion evidence.

Suggested coarse reason mapping:

- permission failures -> `permission_denied`
- missing or detached root -> `folder_unmounted`
- other I/O or OS failures -> `io_error`

### Watched Folder State Updates

On a healthy scan:

- ensure the watched folder row exists
- set `availability_state = "active"`
- clear `last_failure_reason`
- set `last_successful_scan_ts = now`
- set `updated_ts = now`

On an unreachable scan:

- ensure the watched folder row exists
- set `availability_state = "unreachable"`
- set `last_failure_reason` to the coarse classified reason
- set `updated_ts = now`
- do not update `last_successful_scan_ts`

### File Lifecycle Rules

On a healthy scan:

- keep the existing `photo_files` behavior from issue `#25`
- observed files reactivate to `active`
- absent files advance through `missing` and `deleted` according to the grace period

On an unreachable scan:

- do not call the missing-file reconciliation transition path
- do not mark child `photo_files` as `missing`
- do not advance existing `missing` rows to `deleted`
- do not recompute parent `photos.deleted_ts`

This preserves the distinction between:

- “the file is absent during a healthy scan”
- “the storage could not be trusted during this scan”

### Representative Workflow

The existing local `reconcile_directory()` path remains the representative verification flow.

The workflow should support:

1. healthy reconciliation against a watched root
2. a simulated root access failure that marks the watched folder unreachable without mutating file lifecycle state
3. a later healthy reconciliation that clears the unreachable state and resumes normal missing/deleted handling

### Error Handling

The scan helper should classify root failures conservatively.

For this issue:

- if traversal cannot proceed, return an unreachable result instead of partially reconciling
- avoid mixing partial observations with lifecycle advancement
- prefer preserving current file state over making an incorrect deletion inference

This keeps the heuristic safe even if the precise root-cause classification evolves later.

## Testing Strategy

Follow TDD during implementation.

Add tests that verify:

- a healthy scan still marks absent files `missing`
- a healthy scan still advances eligible files from `missing` to `deleted`
- a root access failure marks the watched folder `unreachable`
- a root access failure records a coarse failure reason
- a root access failure does not mutate existing `photo_files` lifecycle state
- a root access failure does not change parent `photos.deleted_ts`
- a later healthy scan restores the watched folder to `active` and clears the failure reason

Use a repeatable local verification path based on the existing watched-folder reconciliation entry point and failure simulation through monkeypatching or a temporary inaccessible path.

## Non-Goals

This issue does not attempt to:

- build a full watched-folder management API
- add UI for unreachable state reporting
- introduce a detailed root-cause taxonomy beyond coarse failure reasons
- support partial reconciliation for partially accessible roots
- redesign ingest-run persistence

## Implementation Notes

The implementation should preserve the current architecture:

- keep `reconcile_directory()` responsible for scan orchestration and root-health classification
- keep `file_reconciliation.py` focused on lifecycle transitions for healthy observations
- keep watched-folder state updates centralized and explicit

This issue is intentionally a conservative first slice: classify root access failure early, persist folder unreachability, and refuse to convert scan failure into deletion evidence.
