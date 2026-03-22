# ADR-0009: Distinguish Unreachable Storage From File Deletion

- Status: Accepted
- Date: 2026-03-21

## Context

The system ingests photos from watched folders that may live on local disks, mounted filesystems, or network-accessible shared storage.

When expected photos are not visible during a scan, there are multiple possible root causes:

- a file was deleted
- a file was moved or renamed
- a folder was removed
- a watched root was unmounted
- the network share is temporarily unreachable
- access permissions changed
- the filesystem produced an I/O error

If the worker treats all absences as simple file deletion, it will make incorrect lifecycle transitions and present misleading operational status to users.

For a family-oriented deployment on local infrastructure, this distinction matters because temporary storage access issues are common and should not be misinterpreted as user-driven deletion.

## Decision

Model observed file absence separately from diagnosed root cause.

The system should distinguish:

- file-instance lifecycle state
- watched-folder availability state
- last observed failure or absence reason

Examples of lifecycle or availability states include:

- `active`
- `missing`
- `deleted`
- `unreachable`

Examples of diagnosed reasons include:

- `path_removed`
- `path_moved`
- `folder_removed`
- `folder_unmounted`
- `network_unreachable`
- `permission_denied`
- `io_error`
- `unknown`

Operationally:

- if the watched root itself is inaccessible, mark the watched folder as unreachable
- do not advance child file instances toward deletion while the root is unreachable
- only treat file disappearance as evidence toward deletion when the watched root is otherwise accessible

## Consequences

- schema design should include availability and reason fields on watched folders and file-instance state
- worker scans must distinguish root-level access failures from path-level absence
- UI and admin diagnostics can report meaningful operational status rather than generic missing-file messages
- soft-delete logic becomes safer because it depends on healthy observations, not only absence

## Alternatives Considered

- Treat all absent files as deleted after a grace period regardless of root accessibility
- Represent only a generic missing state without root-cause classification
- Keep diagnostic causes only in logs and not in the application data model
