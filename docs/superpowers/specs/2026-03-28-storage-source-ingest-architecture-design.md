# Storage Source Ingest Architecture Design

Date: 2026-03-28
Issue: #8

## Context

Phase 1 currently frames ingestion around admin-managed watched folders that the central system can poll directly. The current implementation and README guidance also assume a path contract where the operator provides both:

- a local scan root
- an in-container mount path that the API/UI container can read later

That contract does not match the intended user experience for a family deployment on a local network.

The target use case is:

- a family member uses a workstation or laptop on the local network
- new photos are copied into a shared location, typically SMB/NAS-backed storage
- the central system ingests metadata from that shared location
- the central database remains queryable even when the original photo source is offline
- the UI may show a thumbnail and explain that the original is currently unavailable until the relevant source becomes reachable again

This means catalog availability and original-file availability are intentionally allowed to diverge.

It also means source identity cannot depend on:

- the workstation from which a path was registered
- an IP address
- a host alias
- a user-specific path spelling

The architecture needs a first-class model for shared storage sources and a scan flow that is owned centrally.

## Decision

Redesign Phase 1 ingestion around first-class storage sources rather than raw watched-folder paths.

The system should:

- register logical `storage_sources` as centrally managed SMB/NAS-backed shares
- identify each source with a server-issued marker file stored at the source root
- define `watched_folders` as source-relative folders under a storage source
- run polling, reconciliation, metadata extraction, and thumbnail generation centrally
- persist metadata and cheap thumbnails centrally so catalog results remain usable while originals are offline
- track source availability separately from photo queryability

This design supersedes the current user-facing assumption that operators should provide a `--container-mount-path` for each ingest command.

## Goals

- make storage identity stable across workstation aliases and network path variants
- keep ingest execution centralized
- support multiple watched folders under one storage source
- allow one logical share to be recognized consistently even when multiple users refer to it from different machines
- keep photos queryable when the original source is offline
- show source-specific availability messaging in the UI later
- preserve conservative missing-file handling when a source is unreachable

## Non-Goals

- general support for arbitrary client-local filesystems
- workstation-resident ingest agents
- automatic identity inference for unregistered shares with no marker file
- broad support for removable media workflows beyond copying photos into a registered shared location
- final UI implementation for availability messaging

## Architecture

### Core Entities

Introduce or reframe the domain around these concepts:

- `storage_source`
- `storage_source_alias`
- `watched_folder`
- `photo`
- `photo_file`
- `thumbnail_asset`

`storage_source` represents one logical shared library root, such as a family NAS share. It is the durable identity boundary for original-file availability.

`storage_source_alias` represents one network address or connection spelling that successfully resolves to that source, such as a UNC path or SMB endpoint variant. Aliases are operational access hints, not identity.

`watched_folder` belongs to exactly one `storage_source` and stores a relative path within that source root.

`photo` remains the logical catalog entity. `photo_file` remains the observed file instance and should retain lifecycle state needed for missing and deleted handling.

`thumbnail_asset` is a centrally stored lightweight derivative created during ingest so search and browse remain useful even when originals are offline.

### Source Identity

`storage_source` identity should be anchored by a marker file written at the root of the shared source during registration.

The marker file should contain at minimum:

- a durable source ID issued by the central system
- a format version
- enough integrity protection to prevent accidental collisions or operator confusion

The source marker, not the access path, is the primary identity proof.

This gives the system the following behavior:

- registering a new source creates a `storage_source` record in the central DB
- registration writes a marker file into the source root
- later scans or registration attempts read the marker before trusting the path
- if two different aliases resolve to the same marker, they attach to the same `storage_source`
- if no marker exists, the share is treated as unregistered until the operator explicitly registers it
- if a marker conflicts with DB expectations, the source is flagged for operator intervention rather than guessed

This avoids duplicate logical sources when the same share is known by different workstation-specific names.

### Access Model

The central system is the only ingest worker. It is responsible for:

- resolving an enabled alias for a `storage_source`
- validating the marker file
- scanning watched folders under that source
- extracting metadata
- generating a cheap thumbnail
- updating file lifecycle state
- recording run outcomes and failures

The system should not depend on the machine from which a user initiates an ingest operation. User actions should mutate central configuration, and the central worker should perform the actual scan work against network-reachable shared storage.

### Paths

Paths should be modeled relative to source identity:

- `storage_source.root` is the logical root proved by the marker file
- `watched_folder.relative_path` identifies a folder beneath that root
- `photo_file.relative_path` identifies the file path relative to the watched folder or source, depending on the existing table split

The catalog should stop treating container mount paths as a user-facing ingest concern.

Internally, the worker may still need runtime filesystem resolution details, but those belong to deployment configuration and alias resolution, not to the watched-folder registration contract.

## Ingest Flow

The central polling workflow should become:

1. load enabled `storage_sources` and `watched_folders`
2. choose a reachable alias for a source
3. validate that the source marker matches the expected `storage_source`
4. if the source root is unreachable, record source unavailability and stop before file lifecycle advancement
5. if reachable, enumerate files in enabled watched folders
6. identify photo candidates by file type
7. compute stable file identity inputs such as source-relative path and content hash
8. extract metadata
9. generate and persist a cheap thumbnail centrally
10. upsert logical photo and file-instance records
11. reconcile missing files only for folders whose source was reachable during the scan
12. record run-level stats, timings, and errors

One-shot commands for development or manual backfill can still exist, but they should operate in terms of registered sources and watched folders instead of free-form host/container path pairs.

## Availability Model

The system should explicitly separate:

- `catalog availability`: metadata and thumbnails are queryable from the central DB
- `original availability`: the source is currently reachable for original-file operations

When a source is offline:

- photos remain queryable
- thumbnails remain renderable
- original file actions fail gracefully
- the UI can explain which source is unavailable and what needs to come back online

This model supports the intended user experience where a family member can still find photos in the system even when the workstation or share that hosts originals is not currently reachable.

## Reconciliation Rules

Reconciliation should remain conservative and should operate only when the source root has been validated as reachable for that scan.

Rules:

- reachable source + observed file: mark active and refresh metadata as needed
- reachable source + previously known file absent: advance through missing and deleted policy
- unreachable source: do not infer deletion or missing transitions from that scan
- source becomes reachable again: resume normal reconciliation

This preserves the ADR-backed distinction between “storage unavailable” and “file actually removed.”

## Registration Workflow

The registration flow should be redefined as:

1. operator provides a candidate SMB/NAS share path and credentials or an existing credential reference
2. the system verifies the share is reachable
3. the system checks for an existing marker at the share root
4. if no marker exists, the system creates a new `storage_source` and writes a marker
5. if a marker exists and matches an existing source, the system attaches the alias to that source
6. the operator chooses one or more watched folders relative to that source root

This should replace the mental model of “register any arbitrary path and tell the CLI what container path it maps to.”

## Deduplication And Identity Notes

Logical source identity should come from the marker file.

Operational access should come from aliases.

Photo identity should continue to use stable file evidence, not alias strings. The current path-plus-hash model is still directionally sound, but the path component should be source-relative rather than container-mount-relative.

This means:

- multiple aliases can point to one source
- one source can have multiple watched folders
- duplicate logical sources caused by differing workstation names are prevented at registration time

## Data Model Impact

Phase 1 should expect schema and service changes around these areas:

- add a `storage_sources` table
- add a `storage_source_aliases` table or equivalent alias representation
- move watched-folder identity from free-form path ownership toward `storage_source_id + relative_path`
- persist marker-file metadata needed for validation
- persist source availability state and last failure reason at the source level
- keep watched-folder health if folder-level reporting remains useful, but derive it from source-aware scans
- add centrally managed thumbnail storage metadata

Existing `watched_folders.container_mount_path` is not the right long-term contract for this architecture. If backward compatibility is needed during migration, it should be treated as a temporary implementation field rather than a durable product concept.

## API And CLI Impact

The product contract should shift from path translation to source registration.

Expected operator-facing actions become:

- register a storage source
- manage source aliases or access configuration
- add a watched folder under a source
- enable or disable a watched folder
- request a rescan or backfill for a source or watched folder

The current `photo-org ingest <root> --container-mount-path <path>` flow is a development-era contract and should not remain the primary architecture for Phase 1.

If a CLI remains, it should target central concepts such as:

- `photo-org source register`
- `photo-org watched-folder add`
- `photo-org ingest rescan --source <id>`

## Failure Handling

The system should record failures at the source-aware scan boundary.

Important distinctions:

- source unreachable
- marker missing
- marker mismatch
- credential failure
- watched-folder path missing under an otherwise reachable source
- file-level metadata extraction failure
- thumbnail generation failure

Only the last two should usually allow the scan to continue for sibling files. Root identity or root reachability failures should prevent deletion inference for that scan.

## Testing Strategy

Verification should cover:

- source registration creates a marker and a `storage_source` record
- repeated registration of the same share via a different alias resolves to the existing source
- watched folders are stored relative to a source
- healthy scans ingest metadata and thumbnails
- unreachable sources do not trigger missing/deleted transitions
- reachable scans resume reconciliation after an outage
- query results remain available when originals are offline
- source-level availability messaging has enough backend state to be exposed later

## Phase 1 Epic And Story Changes

Issue `#8` and the current Phase 1 wording should be updated to reflect this architecture.

Recommended Phase 1 reframing:

### Phase 1 Goal

- make the system able to observe a configured set of shared storage sources and keep the central catalog synchronized

### Phase 1 Features

- admin-managed storage sources
- marker-file-based source registration
- source-relative watched folders
- central polling of watched folders by source
- file reconciliation for new, changed, moved, missing, and deleted files
- EXIF and canonical metadata extraction
- central thumbnail generation and persistence
- conservative missing and soft-delete lifecycle
- ingest run tracking and error recording
- detection of unreachable storage with root-cause reporting
- source availability state exposed for later UI use

### Phase 1 Definition Of Done

- an admin can register a shared storage source
- an admin can add a watched folder under that source
- new photos appear in the catalog after background ingestion
- thumbnails remain available even when originals are offline
- temporary source outages do not incorrectly delete data
- the system records and exposes source-aware ingest failures meaningfully

## Superseded Assumptions

This design supersedes these assumptions in the current docs and code:

- watched folders are the top-level identity boundary for ingestion
- the operator must provide an in-container mount path for each ingest invocation
- photo path stability should be modeled primarily around container-visible paths

Those assumptions were workable for early local development, but they are the wrong product contract for the intended family-network deployment model.

## Open Questions

- what exact marker-file format and integrity mechanism should be used
- whether source aliases should be automatically retired after repeated failure or only operator-managed
- whether the central system should store more than one thumbnail size in Phase 1 or start with a single cheap derivative
- how credentials for SMB/NAS access should be stored and rotated

## Recommendation

Adopt this architecture before continuing Phase 1 implementation on Issue `#8`.

Without this change, the team will keep improving a watched-folder plus container-mount workflow that does not match the actual deployment and user model. With this change, Phase 1 can be implemented around the right boundaries: durable source identity, central ingest authority, source-aware reconciliation, and centrally durable metadata plus thumbnails.
