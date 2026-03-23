# Seed Corpus

This directory contains the checked-in offline photo corpus used for end-to-end development, demos, and real-file validation.

## Purpose

The seed corpus exists to give the repository one small, repeatable dataset that can be ingested without network access.

It is intended for:

- end-to-end validation
- demo preparation
- stable fixture references for real-file workflows

It is not intended to replace synthetic fixtures used by unit tests or BDD scenarios.

## Layout

The corpus is organized into nested folders that simulate representative photo-library structure:

- `family-events/`
- `travel/`
- `reference-faces/`
- `misc/no-exif/`

The source of truth for the asset inventory is [`manifest.json`](/mnt/d/Projects/photo-org/.worktrees/feature-issue-19-seed-corpus-load-path/seed-corpus/manifest.json).

## Asset Rules

Every checked-in asset must:

- be safe to redistribute in the repository
- record its source and license metadata in the manifest
- stay small enough for routine repository use
- preserve stable relative paths once committed

Assets may be resized, converted, or metadata-adjusted to create predictable ingest and search behavior.
