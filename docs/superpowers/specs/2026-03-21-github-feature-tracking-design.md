# GitHub Feature Tracking Design

## Context

The project already defines its feature roadmap in [ROADMAP.md](../../ROADMAP.md) as a set of phased deliveries from foundations through packaging and release hardening.

The next step is to represent that roadmap on GitHub in a way that supports day-to-day implementation tracking without requiring a separate GitHub Project board.

The tracking model needs to satisfy these constraints:

- work should be tracked at the feature-slice level rather than only at the phase level
- issues may be implementation-oriented rather than strictly user-facing
- each roadmap phase should have a demoable outcome
- demos do not need to be UI-based; API, worker, CLI, or data-backed demonstrations are acceptable
- parent issues should make the phase completion contract explicit
- child issues should have explicit, formal acceptance criteria
- the issue system should remain easy to query and maintain without excessive process overhead

## Decision

Use a three-part GitHub tracking model:

1. one parent issue per roadmap phase
2. implementation-oriented child issues under each parent
3. a fixed label taxonomy for phase, priority, area, and issue type

This deliberately avoids introducing a GitHub Project board at this stage. The issue hierarchy and labels are sufficient for tracking implementation progress while keeping setup and maintenance costs low.

## Parent Issue Design

Each roadmap phase gets one parent issue with the title:

- `Phase N: <phase name>`

Each parent issue should contain these sections:

### Goal

A short paragraph describing the purpose of the phase, aligned with the corresponding section in [ROADMAP.md](../../ROADMAP.md).

### Demo Capabilities

A flat checklist of concrete capabilities that must be demonstrable before the phase is considered complete.

These capabilities should be observable and runnable in a local development environment using the seed corpus or an equivalent representative setup. A demo capability may be expressed through:

- API behavior
- worker behavior
- CLI behavior
- persisted data state
- UI behavior, where applicable

### Out Of Scope

Items explicitly deferred to later phases so phase closure does not drift.

### Child Issues

A linked checklist of the implementation child issues associated with the phase.

### Completion Criteria

A concise restatement of the conditions for closing the parent issue. Parent closure means the child issues are complete and the listed demo capabilities can actually be demonstrated.

## Child Issue Design

Each implementation child issue should contain these sections:

### Summary

A short paragraph describing the unit of work.

### Why This Matters

A brief explanation of how the issue contributes to the phase goal.

### Scope

A flat checklist of the implementation work included in the issue.

### Non-Goals

A flat list of work that is explicitly excluded from the issue to prevent scope creep.

### Acceptance Criteria

A flat checklist of observable, testable outcomes that must be true before the issue can be closed.

Acceptance criteria should be written as completion conditions, not implementation notes. They should be specific enough that another contributor can evaluate whether the issue is actually done.

Examples:

- the migration creates the required tables, indexes, and constraints
- the worker distinguishes unreachable storage from confirmed deletion states
- the API returns deterministic ordering for photo listing requests
- label provenance records whether an assignment was human-confirmed or machine-applied

### Verification

A short description of how the acceptance criteria will be checked. Depending on the issue, this may include:

- automated tests
- migration checks
- API requests
- worker runs against a representative folder
- manual demo steps

### Dependencies

Optional links to blocking or prerequisite issues.

## Label Taxonomy

Use a small fixed label set.

### Phase Labels

- `phase:0`
- `phase:1`
- `phase:2`
- `phase:3`
- `phase:4`
- `phase:5`
- `phase:6`
- `phase:7`
- `phase:8`

### Priority Labels

- `priority:p0`
- `priority:p1`
- `priority:p2`
- `priority:p3`

### Area Labels

- `area:db`
- `area:api`
- `area:worker`
- `area:web`
- `area:infra`
- `area:search`
- `area:recognition`
- `area:ops`

### Type Labels

- `type:parent`
- `type:implementation`

Labeling rules:

- each parent issue gets one `phase:*` label, one `priority:*` label, and `type:parent`
- each child issue gets one `phase:*` label, one `priority:*` label, `type:implementation`, and one or more `area:*` labels

## Initial Parent Issues

Create one parent issue for each roadmap phase:

1. `Phase 0: Foundations`
2. `Phase 1: Corpus Management And Ingestion`
3. `Phase 2: Browse And Inspect`
4. `Phase 3: Search And Filtering`
5. `Phase 4: Face Labeling Workflow`
6. `Phase 5: Recognition Suggestions`
7. `Phase 6: Operational Admin Features`
8. `Phase 7: Search And Recognition Quality Improvements`
9. `Phase 8: Packaging And Release Hardening`

### Parent Demo Capabilities

#### Phase 0: Foundations

- developer can start the stack locally with one documented path
- database schema exists for the core catalog and labeling entities
- API and worker both use the shared data access layer
- seed corpus can be loaded or referenced consistently in development

#### Phase 1: Corpus Management And Ingestion

- a watched folder can be registered in the system
- worker polling detects new and changed files in that folder
- extracted metadata is persisted for discovered photos
- missing files are soft-handled conservatively rather than hard-deleted
- storage outages are surfaced distinctly from actual deletions
- ingest runs and errors are queryable

#### Phase 2: Browse And Inspect

- cataloged photos can be listed from the backend in a deterministic order
- a single photo can be fetched with its metadata
- detected face regions attached to a photo are retrievable
- ingestion status information needed by the browse flow is exposed

#### Phase 3: Search And Filtering

- text, date, person, and location filters can be applied together
- pagination and sorting are stable and deterministic
- seed-corpus queries return coherent results for representative scenarios

#### Phase 4: Face Labeling Workflow

- people records can be created and managed
- a face can be assigned to or corrected to a person
- label provenance distinguishes human-confirmed from machine-applied data
- permissions for validation actions are enforced

#### Phase 5: Recognition Suggestions

- embeddings are stored and used for nearest-neighbor lookup
- new faces receive candidate suggestions
- threshold policy distinguishes auto-apply, review-needed, and no-suggestion cases
- prediction provenance and model version are stored

#### Phase 6: Operational Admin Features

- watched-folder health and recent ingest runs are visible
- recent ingest failures are inspectable
- folders can be enabled or disabled
- manual rescan or backfill can be triggered
- catalog and labeling work metrics are exposed

#### Phase 7: Search And Recognition Quality Improvements

- at least one ranking improvement measurably changes result usefulness
- duplicate or near-duplicate handling is demonstrable
- recognition quality evaluation and threshold calibration are runnable

#### Phase 8: Packaging And Release Hardening

- a fresh local-network installation is repeatable
- upgrade path including migrations is documented and runnable
- validation automation exists for core release checks
- backup and restore workflow is documented and testable

## Initial Child Issues

These are the initial implementation-oriented child issues to create under each parent issue.

### Phase 0: Foundations

- Define core catalog and labeling schema
- Implement shared database access layer for API and worker
- Establish local Compose-based development stack
- Add repeatable seed-corpus development load path
- Document baseline developer workflow and environment contracts

### Phase 1: Corpus Management And Ingestion

- Implement watched folder persistence and management API
- Build folder polling worker loop
- Implement file reconciliation for new and changed files
- Implement file move detection and identity preservation
- Implement conservative missing-file lifecycle and soft delete rules
- Distinguish unreachable storage from confirmed deletion states
- Extract and persist EXIF and canonical photo metadata
- Record ingest runs, per-file outcomes, and error details
- Expose ingest status and failure information through the backend

### Phase 2: Browse And Inspect

- Implement photo listing endpoint with deterministic ordering
- Implement photo detail endpoint with metadata projection
- Expose detected face regions on photo detail payloads
- Expose ingestion status data needed for browse and inspect workflows

### Phase 3: Search And Filtering

- Implement text search over cataloged photos
- Implement date range filtering
- Implement person-based filtering
- Implement location filtering and proximity search
- Implement facet-style filters such as has-faces and path hints
- Implement deterministic pagination and stable sort semantics
- Define representative seed-corpus query fixtures for search validation

### Phase 4: Face Labeling Workflow

- Implement people management model and API
- Implement face-to-person assignment workflow
- Implement face label correction and reassignment workflow
- Persist explicit label provenance and assignment source
- Enforce separation of human-confirmed and machine-applied labels
- Enforce permissions for face validation actions

### Phase 5: Recognition Suggestions

- Persist face embeddings with `pgvector`
- Implement nearest-neighbor candidate lookup
- Implement threshold-based suggestion policy
- Implement conservative auto-apply behavior for high-confidence matches
- Implement review-needed suggestion state for medium-confidence matches
- Persist prediction provenance and model version metadata

### Phase 6: Operational Admin Features

- Implement watched-folder health reporting
- Implement ingest run history and recent error views in the backend
- Implement folder enable and disable controls
- Implement manual rescan and backfill triggers
- Expose catalog health and pending-work metrics

### Phase 7: Search And Recognition Quality Improvements

- Implement ranking refinements using time, location, and co-occurrence hints
- Implement duplicate and near-duplicate handling
- Improve path-derived metadata labeling support
- Implement recognition evaluation and threshold calibration workflow
- Expose suggestion quality metrics and diagnostics

### Phase 8: Packaging And Release Hardening

- Finalize Compose-based deployment flow
- Implement automated migration execution for packaged environments
- Add CI validation for core application flows
- Add release automation baseline
- Document and verify backup and restore workflow

## Next Actions

Once this design is accepted, the execution sequence is:

1. create the fixed label taxonomy in GitHub
2. create the nine parent issues
3. create the implementation child issues and associate them with the relevant parent issue
4. ensure each parent issue includes explicit demo capabilities and completion criteria
5. use the resulting issue graph as the source of truth for implementation progress
