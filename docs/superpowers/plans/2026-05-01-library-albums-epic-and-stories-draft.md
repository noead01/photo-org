# Draft GitHub Epic And Child Stories: Unified Library + Shareable Albums + Export

Date: 2026-05-01
Source spec: `docs/superpowers/specs/2026-05-01-library-albums-unified-workflow-design.md`

## Purpose

Provide GitHub-ready issue text for one new UI epic and child stories implementing the approved unified Library + Albums direction. This draft is intentionally structured to enable a follow-up de-duplication pass against existing UI issues.

## Proposed New Epic

### Title

`UI EPIC: Unified Library, Shareable Albums, And Export`

### Suggested labels

- `phase:4`
- `priority:p1`
- `type:parent`
- `area:web`

### Body

## Goal

Deliver a unified visual Library workflow that combines browsing and filtering, supports in-context face assignment/confirmation, and enables shareable in-app albums with local export.

## Demo Capabilities

- [ ] users browse and filter photos in one screen (Library)
- [ ] users select single, page, or all-filtered photo scopes
- [ ] users assign/confirm/correct face labels from Library context
- [ ] users save selections to shareable in-app albums backed by photo references
- [ ] album owners share albums with authenticated users (viewer/editor)
- [ ] users export album contents to local filesystem (folder write when supported, ZIP fallback)

## Out Of Scope

- unauthenticated/public sharing links
- cross-tenant sharing
- model-behavior changes for recognition
- destructive source-file operations

## Child Stories

- [ ] Implement unified Library route with merged browse + search state
- [ ] Implement Library selection scope model and action bar
- [ ] Implement Library in-context face assignment and confirmation workflows
- [ ] Implement face-state filters for unassigned and unconfirmed machine labels
- [ ] Implement album domain APIs and persistence contracts
- [ ] Implement album list/detail UI and add-to-album workflows
- [ ] Implement authenticated album sharing with role-based access
- [ ] Implement album export workflow with local write and ZIP fallback
- [ ] Implement legacy route migration and deep-link redirect behavior
- [ ] Implement e2e journey coverage for library-to-album-to-export

## Completion Criteria

This EPIC closes when all child stories are complete and the end-to-end workflow is demonstrable: filter/select in Library -> save to album -> share with another authenticated user -> export successfully with deterministic result reporting.

## Dependencies

- Existing UI foundations from #159, #160, #161
- Existing bulk-action direction from #229 (to be reconciled in dedupe pass)
- New backend contracts for album entities, sharing, and export jobs

---

## Proposed Child Stories

### 1) Unified Library route

**Title**
`Implement unified Library route with merged browse and search state`

**Suggested labels**
- `phase:4`
- `priority:p1`
- `type:implementation`
- `area:web`

**Body**

## Summary

Create a single Library route that combines visual browsing and search/filter controls into one workspace.

## Why This Matters

Users should not context-switch between Browse and Search when visually selecting photos.

## Scope

- add `Library` route as primary entry point
- compose existing browse/search request and rendering patterns into one state model
- keep URL-synced filter state and deterministic pagination/sort behavior
- keep visual photo cards as default result representation

## Non-Goals

- album CRUD
- export execution flows

## Acceptance Criteria

- one screen contains visual results plus filter/search controls
- user can filter without changing routes
- URL round-trip restores equivalent library state
- deterministic pagination behavior matches existing search semantics

## Verification

- unit/integration tests for merged route state
- e2e deep-link and restoration checks

## Dependencies

- #160
- #220

## Potentially supersedes

- parts of #169 (if still open)
- structural intent of #220

---

### 2) Library selection model and action bar

**Title**
`Implement Library selection scope model and action bar`

**Suggested labels**
- `phase:4`
- `priority:p1`
- `type:implementation`
- `area:web`

**Body**

## Summary

Implement selection scopes (`selected`, `page`, `all filtered`) and a scope-aware action bar in Library.

## Why This Matters

Album and export workflows require explicit scope semantics before actions run.

## Scope

- selection reducer/model for photo IDs and filter-scope selection
- action bar with enabled/disabled rules and selection summary
- keyboard and accessibility behavior for selection/actions

## Non-Goals

- concrete album/export API integration details beyond entry-point contracts

## Acceptance Criteria

- users can switch between `selected`, `page`, and `all filtered` scopes
- selection count and scope are explicit and deterministic
- action bar behavior is accessible and route-stable

## Verification

- reducer/component tests
- e2e scope transitions across pagination

## Dependencies

- story 1

## Potentially supersedes

- #230
- #231

---

### 3) Library in-context face labeling workflows

**Title**
`Implement Library in-context face assignment and confirmation workflows`

**Suggested labels**
- `phase:4`
- `priority:p1`
- `type:implementation`
- `area:web`

**Body**

## Summary

Expose assign/confirm/correct interactions for detected faces directly in Library quick-panel context.

## Why This Matters

Labeling throughput and confidence improve when users act where they are already selecting photos.

## Scope

- show face overlays and label-source badges in Library preview panel
- support assign for unassigned faces
- support confirm/correct for machine-labeled faces
- reuse deterministic feedback/error handling from existing detail workflow

## Non-Goals

- people-management CRUD
- recognition-suggestions queue

## Acceptance Criteria

- users can assign, confirm, and correct without mandatory navigation to photo detail
- provenance context remains visible during actions
- conflict/permission errors are deterministic and recoverable

## Verification

- component tests for action variants and state updates
- e2e flow across multiple photos

## Dependencies

- #161
- #183
- #184
- #185
- #186
- #189

## Potentially supersedes

- parts of #187 (navigation workflow)

---

### 4) Face-state filters

**Title**
`Implement face-state filters for unassigned and unconfirmed machine labels`

**Suggested labels**
- `phase:4`
- `priority:p1`
- `type:implementation`
- `area:web`

**Body**

## Summary

Add filter affordances for `unassigned faces` and `machine-labeled unconfirmed` in Library.

## Why This Matters

Users need direct ways to focus labeling work queues.

## Scope

- add two typed face-state filters with chip/state summary behavior
- integrate filters with URL-synced query state
- expose counts where API supports facets

## Non-Goals

- ML threshold policy changes

## Acceptance Criteria

- both filters can be applied/removed deterministically
- filter state persists in URL and deep-link restore
- resulting set aligns with backend semantics

## Verification

- unit tests for serialization/parsing
- integration tests for request payload mapping

## Dependencies

- #160
- backend face-state filter contract (new)

## Potentially supersedes

- extension of #178

---

### 5) Album domain APIs and persistence

**Title**
`Implement album domain APIs and persistence for photo-reference collections`

**Suggested labels**
- `phase:4`
- `priority:p1`
- `type:implementation`
- `area:web`

**Body**

## Summary

Deliver album APIs and persistence for reference-based collections and membership operations.

## Why This Matters

Shareable albums must exist as durable DB entities before UI workflows can rely on them.

## Scope

- create `albums`, `album_items`, and baseline API endpoints
- support create/list/detail/update/delete and batch add/remove membership
- deterministic duplicate handling and summary responses

## Non-Goals

- public sharing
- export packaging details

## Acceptance Criteria

- album CRUD and membership APIs are available and tested
- duplicate photo add behavior is explicit and idempotent/conflict-defined
- pagination and access boundaries are deterministic

## Verification

- API tests for CRUD, membership, and conflicts

## Dependencies

- backend implementation slice (new)

## Potentially supersedes

- backend dependency placeholder in #235

---

### 6) Albums UI and add-to-album flows

**Title**
`Implement Albums UI and add-to-album workflows from Library selection`

**Suggested labels**
- `phase:4`
- `priority:p1`
- `type:implementation`
- `area:web`

**Body**

## Summary

Implement Albums route (list/detail) and connect Library selection actions to create/add album flows.

## Why This Matters

Users need a reusable, inspectable destination for selected photo sets.

## Scope

- album list and album detail pages
- add-to-existing and create-new album actions from Library
- deterministic completion summaries for add operations

## Non-Goals

- advanced album curation tooling

## Acceptance Criteria

- user can create album from current selection scope
- user can add selection to existing album
- album detail shows referenced photos and membership updates

## Verification

- component and route integration tests
- e2e creation and add-existing flows

## Dependencies

- stories 1, 2, 5

## Potentially supersedes

- #235

---

### 7) Authenticated album sharing

**Title**
`Implement authenticated album sharing with viewer/editor roles`

**Suggested labels**
- `phase:4`
- `priority:p1`
- `type:implementation`
- `area:web`

**Body**

## Summary

Implement in-app sharing controls for albums with role-based access (viewer/editor).

## Why This Matters

Albums are collaborative artifacts, not just local personal lists.

## Scope

- share management UI (grant/change/revoke)
- API integration for role assignments
- role-aware UI gating in album detail and add/remove flows

## Non-Goals

- unauthenticated share links
- invitation email workflows

## Acceptance Criteria

- owners can grant/revoke viewer/editor access to authenticated users
- shared users only see allowed actions
- permission errors are explicit and deterministic

## Verification

- API tests for ACL enforcement
- e2e owner vs shared-user role matrix

## Dependencies

- story 5
- story 6

---

### 8) Album export workflow

**Title**
`Implement album export workflow with local folder write and ZIP fallback`

**Suggested labels**
- `phase:4`
- `priority:p1`
- `type:implementation`
- `area:web`

**Body**

## Summary

Implement `Export album to...` from album detail with browser capability detection and deterministic fallback behavior.

## Why This Matters

Users need a reliable external handoff of curated album contents.

## Scope

- export entry point from album detail
- capability detection for directory-write API
- folder-write happy path where supported
- ZIP fallback path where not supported
- completion summary with exported/skipped counts and reasons

## Non-Goals

- cloud destination connectors

## Acceptance Criteria

- user can export from album detail
- supported browsers offer local folder write flow
- unsupported browsers receive ZIP fallback without dead-end UX
- export results are clearly reported

## Verification

- UI tests for capability branches
- e2e export scenarios for folder-write and ZIP fallback

## Dependencies

- story 6
- export backend contract (new)

## Potentially supersedes

- #232
- #233
- #237 (partially, status surface reuse possible)

---

### 9) Legacy route migration

**Title**
`Implement browse/search to Library redirects with state-preserving migration`

**Suggested labels**
- `phase:4`
- `priority:p1`
- `type:implementation`
- `area:web`

**Body**

## Summary

Provide transition-safe redirects from legacy `/browse` and `/search` routes into `Library` while preserving state continuity.

## Why This Matters

Migration should not break existing deep links or user muscle memory.

## Scope

- route redirects from legacy entry points
- map legacy query params into Library-compatible URL state
- preserve focus/return behavior where feasible

## Non-Goals

- long-term support for duplicate route implementations

## Acceptance Criteria

- legacy route URLs resolve into Library without losing core state intent
- no shell navigation regressions
- deterministic fallback for unsupported/invalid legacy params

## Verification

- route tests and e2e deep-link checks

## Dependencies

- story 1
- #179

---

### 10) E2E journeys for Library->Album->Export

**Title**
`Implement end-to-end journey coverage for library selection, album sharing, and export`

**Suggested labels**
- `phase:4`
- `priority:p1`
- `type:implementation`
- `area:web`

**Body**

## Summary

Add executable journey coverage for the new workflow from selection through sharing and export.

## Why This Matters

This workflow crosses route boundaries and role contexts; regressions are high-risk without journey tests.

## Scope

- journey docs and traceability entries
- e2e tests for:
  - build album from filtered library scope
  - share with second authenticated user
  - export with capability-aware behavior

## Non-Goals

- exhaustive browser compatibility matrix beyond target support policy

## Acceptance Criteria

- journey IDs and docs map to executable specs
- workflow assertions are deterministic and role-aware
- failures are attributable to specific journey steps

## Verification

- run journey suite in CI and local

## Dependencies

- stories 1-9
- existing journey infra from #208 and #219

---

## Initial De-duplication Candidates For Next Review

Likely overlapping/open items to evaluate for closure, merge, or retargeting:

- Epic overlap: #229 `UI EPIC: Phase 3 Search Result Bulk Actions`
- Story overlap: #230, #231, #232, #233, #235, #237
- Structural overlap: #220 (shared browse/search primitives)
- Potential partial overlap: #187 (multi-item labeling navigation)

No closure actions are taken in this draft; this list is for the explicit review pass requested by the team.

## Existing Issue Review Matrix (Proposed)

Status snapshot date: 2026-05-01

### Existing epic-level issues

- #229 `UI EPIC: Phase 3 Search Result Bulk Actions` (open)
  - Proposed disposition: **Close as superseded** once the new unified epic is created.
  - Reason: scope is largely subsumed by the new direction and now also expands beyond Search-only context into Library + Albums + sharing.

- #161 `UI EPIC: Phase 4 Face Labeling Workflow` (open)
  - Proposed disposition: **Keep open**.
  - Reason: still the parent for people-management and core face-labeling slices; new epic should depend on it and extend it into Library context.

### Existing story-level issues

- #230 selection scope model (open)
  - Proposed disposition: **Retarget and keep**.
  - Action: update title/body from Search-specific to Library-scoped selection semantics.

- #231 bulk action bar (open)
  - Proposed disposition: **Retarget and keep**.
  - Action: move from Search-results context to Library action bar context.

- #232 destination-folder copy flow (open)
  - Proposed disposition: **Merge into new export story**.
  - Action: close as superseded after migration notes are copied.

- #233 ZIP export (open)
  - Proposed disposition: **Keep as fallback sub-slice** under album export story.
  - Action: retarget to explicit fallback behavior in album export.

- #235 save as collection/album (open)
  - Proposed disposition: **Retarget and keep**.
  - Action: rename to album reference workflow, align with album entity + sharing model.

- #237 bulk-action status surface (open)
  - Proposed disposition: **Keep, broaden**.
  - Action: treat as shared async-job feedback surface used by album export and future bulk operations.

- #234 metadata bulk editor (open)
  - Proposed disposition: **Keep separate, de-prioritize**.
  - Reason: valuable but not required for the approved Library+Albums journey baseline.

- #236 CSV/JSON manifest export (open)
  - Proposed disposition: **Keep separate, de-prioritize**.
  - Reason: useful adjunct feature, not part of must-have journey.

- #220 browse/search refactor primitives (open)
  - Proposed disposition: **Retarget and keep**.
  - Action: recast as migration/refactor story for Library unification internals.

- #187 multi-item labeling navigation (open)
  - Proposed disposition: **Keep open (possible partial overlap)**.
  - Reason: can still provide value for detail-centric workflows even after in-context Library actions.

## Recommended sequencing for cleanup

1. Create new unified epic and child-story set.
2. Immediately retarget #230, #231, #233, #235, #237, #220 to the new epic.
3. Close #229 (superseded) and close #232 after extracting any unique acceptance criteria.
4. Leave #234 and #236 open but move to lower priority/milestone if needed.
5. Keep #161 and #187 open; reassess #187 after Library face-workflow implementation lands.
