# UI Layer EPICs And Stories Design

Date: 2026-04-26
Scope: UI planning artifacts (GitHub EPIC + child story issues), ready to create and refine
Roadmap alignment: Phase 2 through Phase 6

## Summary

Define a phase-aligned UI issue structure that can be created directly in GitHub:

- 5 UI EPICs aligned to roadmap phases (`Phase 2` to `Phase 6`)
- 6-10 workflow-first child stories per EPIC
- explicit dependency links to backend issues when UI work depends on not-yet-delivered contracts
- global app-shell foundations folded into the Phase 2 UI EPIC

This design is for planning and issue authoring, not implementation.

## Goals

- create UI EPIC and story definitions that are immediately usable as GitHub issues
- align UI planning to existing project phase labels and parent/child tracking style
- define child stories as user-observable workflows with clear acceptance criteria
- allow stories that depend on planned backend work, with explicit blockers

## Non-Goals

- no code implementation in this document
- no sprint-point estimation model
- no GitHub Project board design
- no redesign of the backend roadmap or phase taxonomy

## Decision Snapshot

- EPIC horizon: end-to-end UI through recognition and operations (`Phase 2` to `Phase 6`)
- EPIC structure: phase-by-phase
- Story depth: balanced granularity (6-10 stories per EPIC)
- Dependency model: include stories that depend on planned backend issues, with explicit dependency links
- App-shell scope: folded into Phase 2 UI EPIC (not a standalone EPIC)

## Visual Companion Artifacts

These mockup screens were used to validate story-map scope during brainstorming:

- `.superpowers/brainstorm/2-1777238447/content/ui-phase-story-map-mockups-v1.html`
- `.superpowers/brainstorm/2-1777238447/content/ui-epic-topology-options.html`
- `.superpowers/brainstorm/2-1777238447/content/ui-epic-scope-options.html`

## GitHub Labeling And Structure

Follow existing tracking conventions:

- EPIC labels: `phase:*`, `priority:*`, `type:parent`
- Story labels: `phase:*`, `priority:*`, `type:implementation`, `area:web`
- Story links: each story must link to parent EPIC
- Dependency links: each story with backend dependency must link the blocking issue(s)

## Issue Authoring Template

### EPIC issue sections

- Goal
- Demo Capabilities
- Out Of Scope
- Child Stories
- Completion Criteria
- Dependencies (optional, for cross-phase/backend prerequisites)

### Child story issue sections

- Summary
- Why This Matters
- Scope
- Non-Goals
- Acceptance Criteria
- Verification
- Dependencies

## EPIC And Story Catalog

### UI EPIC: Phase 2 Browse And Inspect

Goal:

- provide the foundational UI shell and the browse/detail experience over cataloged photos.

Child stories:

1. App shell frame with global header/nav/content regions
2. Logged-in user menu (identity, account actions, sign-out entry)
3. Global navigation state model (active route, page title, breadcrumbs if present)
4. Responsive layout behavior for desktop/tablet/mobile
5. Global loading/error/notification surface patterns
6. Photo gallery grid with deterministic ordering and pagination controls
7. Photo detail view with metadata presentation
8. Face-region overlays in photo detail
9. Ingest-status visibility in gallery/detail contexts
10. Browse/detail empty, loading, and failure states with keyboard-accessible focus behavior

Dependencies:

- backend photo list/detail contracts and ingest-status fields (Phase 2 backend issues)

### UI EPIC: Phase 3 Search And Filtering

Goal:

- make catalog exploration meaningfully searchable via composable filter workflows.

Child stories:

1. Search bar with tokenized text query behavior
2. Date-range filter UI with inclusive boundaries
3. Person filter UI with fuzzy-name matching behavior
4. Location-radius filter inputs (lat/lon/radius) and validation
5. Facet panel (`has_faces`, path hints) with counts and toggles
6. URL-synced filter state and restorable deep links
7. Stable sort and deterministic pagination under filter changes
8. Search result/no-match/error messaging variants

Dependencies:

- backend search issues for text/date/person/location/facets/pagination (Phase 3 issue set)

### UI EPIC: Phase 4 Face Labeling Workflow

Goal:

- support people management and reliable face-label assignment/correction workflows.

Child stories:

1. People management screen (create/list/rename/delete)
2. Face-to-person assignment interaction from photo detail
3. Label correction/reassignment flow for previously assigned faces
4. Provenance badges/details for label origin visibility
5. Permission-aware action gating and read-only affordances
6. Multi-item labeling workflow navigation (next/previous/return-to-results)
7. Assignment/correction success and failure feedback states
8. Conflict/blocked-action UX for backend `409` or permission-denied responses

Dependencies:

- Phase 4 backend issues for people management, assignment, correction, provenance, and permission enforcement

### UI EPIC: Phase 5 Recognition Suggestions

Goal:

- provide a trustworthy suggestion-review flow that improves labeling throughput without unsafe automation.

Child stories:

1. Suggestion review queue for review-needed faces
2. Candidate card UI with confidence-band communication
3. Accept suggestion action flow
4. Reject suggestion action flow
5. Correct-to-different-person flow from suggestion context
6. Provenance/model-version detail panel for transparency
7. Throughput aids (quick next item, keyboard shortcuts where appropriate)
8. Queue empty/error/loading states with clear operator guidance

Dependencies:

- Phase 5 backend issues for candidate lookup, threshold policy, review-needed state, and prediction provenance

### UI EPIC: Phase 6 Operational Admin Features

Goal:

- deliver an operator-oriented console for source health, failures, manual controls, and workload visibility.

Child stories:

1. Storage-source health dashboard table
2. Ingest failure timeline with inspectable error details
3. Source enable/disable control workflows with confirmation and outcome feedback
4. Manual rescan/backfill trigger UI and status tracking
5. Catalog metrics cards (catalog size, face counts, unlabeled, pending)
6. Filtering/sorting controls for source-health and failure views
7. Admin dashboard empty/loading/error/degraded mode states
8. Permission-aware admin action gating and non-destructive defaults

Dependencies:

- Phase 6 backend issues for health reporting, run/error history, source controls, rescan/backfill, and metrics APIs

## Story Acceptance-Criteria Quality Bar

Each child story should include acceptance criteria that are:

- observable in UI behavior
- explicit about `loading`, `empty`, `error`, and `success` states where relevant
- explicit about URL/state persistence for filter workflows
- explicit about deterministic ordering/pagination expectations where applicable
- explicit about accessibility baseline for primary interactions (keyboard + semantic naming)

## Dependency Policy For Future Backend Contracts

When a UI story depends on not-yet-delivered backend work:

1. include blocking backend issue link(s) in `Dependencies`
2. include a `Non-Goals` item that forbids fake or speculative backend semantics
3. scope any unblockable frontend work to scaffolding/interaction/state behavior that remains valid after backend delivery

## GitHub Creation Sequence

1. create the 5 UI EPIC issues (`Phase 2` through `Phase 6`)
2. create child story issues under each EPIC using the catalog above
3. apply labels and parent links for every issue
4. add backend dependency links for stories with contract blockers
5. refine acceptance criteria in GitHub without changing EPIC topology

## Open Questions

- none for this planning slice; scope and structure are approved.
