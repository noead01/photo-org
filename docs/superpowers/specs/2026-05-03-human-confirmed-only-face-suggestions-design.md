# Human-Confirmed-Only Face Suggestions Design

Date: 2026-05-03
Parent: #161
Topic: Face suggestion workflow with proactive recompute and certainty-aware person filtering

## Summary

Move face recognition to a strictly human-confirmed assignment model:

- only human actions may assign or reassign `faces.person_id`
- machine output is advisory (`machine_suggested`) and never authoritative
- suggestion quality improves as more `human_confirmed` labels are collected for a person
- background workers proactively recompute suggestions after human review events
- Library person filtering supports certainty modes (`human_only` vs heuristic-inclusive)

## Goals

- Remove machine auto-assignment behavior.
- Improve suggestion accuracy by learning from multiple human-confirmed faces per person.
- Keep suggestions ranked and clickable in photo-detail assignment UI.
- Support person filtering by certainty mode in Library.
- Keep provenance and auditability explicit for both human and machine states.

## Non-Goals

- Introducing external model hosting or online training infrastructure.
- Replacing current face embeddings with a new embedding model in this slice.
- Building a global active-learning UI for bulk review (future work).

## Product Decisions (Validated)

- `machine_applied` is removed from active behavior and data constraints.
- `human_confirmed` is the only trusted assignment state.
- Suggestions are always heuristic, never 100% certainty.
- Recompute runs proactively in background after human review changes.
- Debounce/coalescing is required for future rapid confirm/reject flows.
- Since backward compatibility is not required yet, schema changes can be made directly in the initial Alembic revision.

## Current State Constraints

- Candidate lookup currently supports `auto_apply`, `review_needed`, and `no_suggestion`.
- API currently writes `machine_applied` rows and can set `faces.person_id` automatically.
- Person filter currently matches person presence only and does not distinguish certainty classes.

## Target State

### Assignment Authority

- `POST /faces/{id}/assignments`, `POST /faces/{id}/corrections`, and `POST /faces/{id}/confirmations` remain the only write paths for `faces.person_id`.
- Candidate/suggestion endpoints never mutate `faces.person_id`.

### Suggestion State

- Machine scoring writes suggestion state only.
- Suggestions are versioned, replaceable, and explicitly linked to scorer/model metadata.

### Certainty Semantics

- `human_only` means latest effective label source is `human_confirmed`.
- Heuristic mode includes machine suggestions above configured threshold and below certainty semantics of human-confirmed labels.

## Data Model Design

## 1) `face_labels` source normalization

- Remove `machine_applied` from allowed label sources.
- Allowed values become:
  - `human_confirmed`
  - `machine_suggested`

Rationale:

- `face_labels` remains the event/provenance ledger.
- Machine suggestions are advisory events/state references, not assignment commits.

## 2) New `person_representations` table

Add materialized representation per person for fast shortlist and quality scaling.

Proposed columns:

- `person_id` (PK/FK `people.person_id`)
- `centroid_embedding` (vector/JSON aligned with `faces.embedding` type)
- `confirmed_face_count` (int, not null)
- `dispersion_score` (float, nullable)
- `representation_version` (bigint/int, not null)
- `computed_ts` (timestamp, not null)
- `model_version` (string, not null)
- `provenance` (json, nullable)

Rationale:

- Avoid recomputing centroid/stats inline on every suggestion lookup.
- Provide version boundary for stale-suggestion replacement.

## 3) New `face_suggestions` table

Persist top-N heuristic candidates per unlabeled face.

Proposed columns:

- `face_suggestion_id` (PK)
- `face_id` (FK `faces.face_id`, cascade delete)
- `person_id` (FK `people.person_id`, cascade delete)
- `rank` (int, not null)
- `confidence` (float, not null)
- `centroid_distance` (float, nullable)
- `knn_distance` (float, nullable)
- `representation_version` (int/bigint, not null)
- `scoring_version` (string, not null)
- `model_version` (string, not null)
- `provenance` (json, nullable)
- `created_ts` (timestamp, not null)
- `updated_ts` (timestamp, not null)

Constraints and indexes:

- unique (`face_id`, `person_id`, `representation_version`, `scoring_version`)
- unique (`face_id`, `rank`, `representation_version`, `scoring_version`)
- index on (`face_id`, `updated_ts`)
- index on (`person_id`, `confidence`)

Rationale:

- Decouples suggestion snapshots from assignment event ledger.
- Enables deterministic replacement of stale snapshots.

## 4) Initial migration update policy

- Update `apps/api/alembic/versions/20260321_000001_initial_schema.py` directly.
- Keep schema source of truth aligned in `packages/db-schema/photoorg_db_schema/schema.py`.
- No follow-up compatibility migration required at this stage.

## Scoring and Ranking Design

## Hybrid Scoring Pipeline

For each unlabeled face:

1. Generate shortlist by nearest `person_representations.centroid_embedding`.
2. Re-rank shortlist using k-NN over that person’s `human_confirmed` exemplars.
3. Combine signals into final confidence:
   - centroid similarity contribution
   - exemplar k-NN contribution
   - sample-size reliability boost (`confirmed_face_count`)
   - dispersion penalty (`dispersion_score`)
4. Store top-N candidates ordered by confidence descending.

Notes:

- Confidence remains heuristic `[0,1]`.
- No confidence value is treated as certainty.
- Scoring formula version must be explicit (`scoring_version`) for future tuning.

## Recompute Workflow (Proactive)

## Triggers

Any successful human-reviewed mutation emits a recompute signal:

- assignment
- correction
- confirmation

Signal includes:

- `face_id`
- affected `person_id`(s)
- event timestamp

## Debounced Batch Processor

- Buffer events for short debounce window.
- Coalesce by person and face keys.
- Latest action wins per face within window.
- Emit one recompute job per coalesced batch.

## Worker Steps

1. Recompute person representations for affected people.
2. Resolve impacted unlabeled faces (full unlabeled set initially; optimize later).
3. Re-score and replace `face_suggestions` snapshots atomically per face/version.
4. Mark stale snapshots superseded by version (or delete eagerly).

## Operational Guarantees

- Jobs are idempotent.
- Retries are safe.
- UI can fallback to on-demand score refresh if queue lag exceeds threshold.

## API Contract Changes

## Candidates API

- Remove auto-assignment side effect from candidate lookup.
- Remove `auto_applied_assignment` response contract.
- Return:
  - ranked candidates
  - suggestion policy metadata
  - version metadata (`representation_version`, `scoring_version`, `model_version`)

## Recognition policy

- Remove `auto_apply` decision path.
- Retain thresholding only for visibility class (e.g., show vs no suggestion).

## Search/Library filters

Add filters:

- `person_certainty_mode: "human_only" | "include_suggestions"`
- `suggestion_confidence_min?: float`

Semantics:

- `human_only`: filter by photos with person presence backed by human-confirmed labels.
- `include_suggestions`: include photos matching either human-confirmed labels or machine suggestions above threshold.

## Facets

Add certainty-aware people facets:

- `people_human_confirmed`
- `people_machine_suggested`

## UI Behavior

## Photo detail suggestion box

- Keep suggested names clickable.
- Show confidence/resemblance ordering descending.
- Selecting a suggestion triggers existing human assignment endpoint.

## Provenance and badges

- `human_confirmed` remains 100%-certainty UX class.
- machine suggestions are clearly marked heuristic.

## Library person filter UX

- Certainty mode toggle:
  - Human-reviewed only
  - Include heuristic suggestions
- Optional threshold control when heuristic mode is enabled.
- Filter chips reflect certainty mode and threshold.

## Testing Strategy

## Backend tests

- No candidate API path mutates `faces.person_id`.
- `machine_applied` source rejected/absent from schema and service behavior.
- Representation recompute correctness for centroid/count/dispersion.
- Suggestion snapshot replacement is deterministic by version.
- Search filter certainty-mode behavior matches contract.

## Integration tests

- Burst human confirmations produce coalesced recompute batches.
- Recompute queue lag/fallback behavior.
- End-to-end: human-confirmed additions improve ranking for same person.

## UI tests

- Suggested names sorted by confidence and clickable.
- Human-reviewed vs heuristic filter mode behavior in Library.
- Heuristic threshold affects result inclusion deterministically.

## Observability

Add metrics:

- recompute queue depth and lag
- recompute batch size after debounce
- suggestion acceptance rate by confidence bucket
- confirmation/correction rate for top-ranked suggestions

Add logs:

- representation version updates per person
- face suggestion replacement counts per recompute run

## Risks and Mitigations

- Risk: expensive full-unlabeled recompute.
  - Mitigation: ship full recompute first, then optimize impacted-face selection and ANN scoping.
- Risk: confidence miscalibration.
  - Mitigation: explicit scoring versioning and bucketed acceptance metrics.
- Risk: stale suggestions visible during queue lag.
  - Mitigation: version checks + optional on-demand refresh path.

## Acceptance Criteria Mapping

- Human-only assignment authority:
  - no machine write to `faces.person_id`.
- Improved suggestion quality with more confirmed labels:
  - person representations and hybrid scoring.
- Clickable sorted suggestions:
  - preserved and ranked by heuristic confidence.
- Library certainty filtering:
  - `human_only` and heuristic-inclusive modes with threshold support.
- Debounced background recompute:
  - coalesced jobs triggered by human review events.
