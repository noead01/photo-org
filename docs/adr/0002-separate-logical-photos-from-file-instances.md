# ADR-0002: Separate Logical Photos From File Instances

- Status: Accepted
- Date: 2026-03-21

## Context

The system must monitor user-configured folders, ingest photos found in those folders, and handle renames, moves, duplicates, and deletions correctly.

If path is treated as the identity of a photo, then:

- moving a file creates a false new photo
- renaming a file appears as delete plus insert
- the same content in multiple locations becomes ambiguous

Content hash provides a stable identity signal for the file contents, but it should not be the primary key of the database row.

## Decision

Model the domain with:

- a logical `photos` table using a UUID primary key
- a unique `sha256` content hash on `photos`
- a separate `photo_files` table representing observed filesystem instances

`photo_files` should capture path-specific and scan-specific state such as:

- watched folder membership
- full path
- filename and extension
- first seen / last seen
- missing or deleted timestamps

## Consequences

- the same photo content can be observed at multiple paths without duplicating the logical photo
- moves and renames can be represented as changes to file-instance records
- soft deletion of a logical photo can depend on whether any active file instances remain
- search facets and metadata derived from path segments can be stored as hints rather than identity

## Alternatives Considered

- Use file path as the identity of a photo
- Use content hash as the primary key of `photos`
- Treat every file instance as an independent photo row
