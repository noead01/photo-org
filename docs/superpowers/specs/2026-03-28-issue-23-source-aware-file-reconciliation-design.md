# Issue 23 Source-Aware File Reconciliation Design

Date: 2026-03-28
Issue: #23

## Context

The source-registration and watched-folder work is already in place, and the polling loop now validates a registered storage source before scanning. The remaining gap is that file reconciliation still carries legacy path assumptions in the ingest path:

- watched-folder scan setup still has legacy helpers based on raw scan paths
- canonical photo identity is still built from alias-resolved or container-style paths
- tests and helpers still encode container-path terminology even when the worker is operating on a registered source

That leaves new and changed file handling too close to runtime path spellings, which is the wrong trust boundary for source-backed ingestion.

## Goal

Make new and changed file reconciliation source-aware so the ingest path derives stable identity from registered source ownership and source-relative paths rather than alias-specific or container-specific path contracts.

## Non-Goals

- schema-wide migration of all historical path fields
- move detection
- thumbnail redesign
- unrelated cleanup outside ingest, reconciliation, and directly touched tests/docs

## Decision

Treat `storage_source_id` plus source-relative paths as the identity boundary for source-backed reconciliation.

For the issue-23 slice:

- registered-source polling should derive canonical photo identity from the validated source, the watched folder's persisted relative path, and the file path relative to that watched folder
- source-backed reconcile flows should not depend on raw scan-path-derived watched-folder identifiers
- legacy `container_mount_path` references should be removed from the touched source-backed ingest/reconciliation code where they are no longer needed
- missing/deleted lifecycle behavior must remain conservative and only run after source validation succeeds

## Design

### Canonical file identity

When polling a registered source, the worker already knows:

- which `storage_source_id` was validated
- which persisted `watched_folder_id` is being scanned
- the watched folder's persisted source-relative path
- the file path relative to the watched folder root

That is enough to build a source-aware logical path. The canonical path used for `photo_id`, `photos.path`, queue payloads, and comparisons should be derived from those persisted values rather than from the alias root or a container mount path.

This keeps the same file stable even if the worker reaches the same source through a different alias later.

### Reconciliation boundary

Reconciliation should continue to operate on the persisted `watched_folder_id`, with observed file membership expressed as file paths relative to that watched folder. The worker should only advance missing/deleted transitions after:

1. a source alias is resolved
2. the source root is validated
3. the source marker matches the expected `storage_source_id`

If any of those checks fail, the source and watched folder remain marked unreachable and file lifecycle state must not advance.

### Legacy path cleanup

Issue `#23` is also the point to remove stale container-path assumptions from the touched source-aware code. That does not require deleting every historical field immediately. It does require:

- stopping new source-backed identity derivation from using `container_mount_path`
- updating tests and helpers to assert source-aware behavior directly
- renaming or simplifying local helpers where their old names still imply a container-path contract

## Testing

Add or update focused tests that prove:

- the same registered source scanned through different aliases resolves to the same canonical photo identity
- new and changed files under a registered watched folder reconcile correctly
- marker mismatch and unreachable-source failures do not advance missing/deleted lifecycle
- touched helpers and docs no longer rely on legacy container-path language for source-backed polling behavior
