## Iterative Development Model

This project should be developed against a deliberately small, representative corpus first, then scaled up only after the user experience and core workflows are stable.

The goal is not to prove that the final architecture can handle a large photo library on day one. The goal is to make the end-to-end experience correct, fast to change, and easy to evaluate with a tiny dataset that exposes the real product decisions.

## Seed Corpus

Use a fixed seed corpus of approximately:

- 20 to 50 photos
- 3 to 6 people
- A mix of single-person, multi-person, and no-face photos
- At least 2 duplicate or near-duplicate photos
- At least 2 small time-based clusters such as "birthday" and "vacation"
- A few photos with incomplete metadata or ambiguous faces

The seed corpus may be stored outside the repo when necessary, but the current Phase 0 workflow uses a checked-in offline corpus under `seed-corpus/`.

The repo should contain:

- a manifest describing the seed dataset
- deterministic IDs and labels used by tests
- fixtures or scripts that can load the corpus into the local development database

The checked-in corpus should be treated as a curated repository asset:

- every file must be safe to redistribute in-repo
- every file must record source and license metadata in the manifest
- folder layout should remain stable so end-to-end tests can refer to known paths

Synthetic fixtures remain preferred for unit tests and BDD scenarios.

## Product Questions To Answer Early

The seed corpus exists to answer these questions quickly:

- What is the primary landing experience for browsing and searching photos?
- How should face suggestions be presented so correction is fast and obvious?
- Which facets matter to users in practice?
- What confidence thresholds produce acceptable auto-labeling behavior?
- How should duplicates and near-duplicates appear in the UI?
- What does "unknown person" look like as a first-class workflow?

If a feature does not improve one of these questions on the seed corpus, it should not be prioritized yet.

## Development Principle

Build vertical slices, not infrastructure islands.

Each iteration should produce a user-observable workflow that can be demonstrated on the seed corpus. Prefer a simple implementation that works on 30 photos over a scalable design that has not been validated by real interaction.

## Phase 0: Seed Dataset And Demo Path

Before building more features, establish:

- one canonical local database for development
- one repeatable seed-data load path
- one simple UI or API demo path showing the corpus
- one short walkthrough of the intended end-user flow

Definition of done:

- a new developer can load the seed corpus in minutes
- the app can show all seed photos with stable IDs and metadata
- screenshots or a short walkthrough can be generated from the same corpus every time

## Phase 1: Browse And Inspect

First vertical slice:

- list photos
- view a photo
- show detected faces for that photo
- show basic metadata and tags

Ignore advanced ranking and vector search here unless they improve this slice immediately.

Definition of done:

- a user can move from gallery view to photo detail without confusion
- face boxes and person labels are visible and understandable
- empty states are clear for photos with no faces or missing metadata

## Phase 2: Search And Facets

Second vertical slice:

- text search over path, tags, and simple metadata
- faceted filtering by date, tags, people, and "has faces"
- deterministic pagination

Definition of done:

- users can reliably narrow the seed corpus to a specific event or person
- facet counts make sense on the small corpus
- search and filtering behavior feels coherent before optimization work begins

## Phase 3: Labeling Loop

Third vertical slice:

- assign or correct a person label on a face
- preserve provenance and confidence
- surface unknown faces as actionable work

Definition of done:

- the correction flow is faster than editing rows manually
- every label change is explainable in the UI or API
- the system state remains understandable after repeated edits

## Phase 4: Suggestions And Similarity

Only after the labeling loop is usable:

- add nearest-neighbor face suggestions
- rank candidates with simple heuristics
- evaluate suggestion quality on the seed corpus before generalizing

Definition of done:

- suggestions reduce user effort on the seed corpus
- wrong suggestions are cheap to reject
- quality is measured with fixture-based evaluation, not only intuition

## Phase 5: Scale-Up Readiness

Scale after the product interaction model is stable.

Readiness checklist:

- the seed corpus workflows feel good in repeated use
- API contracts are stable enough to support a UI
- tests cover the main happy paths and correction paths
- seed-data loading is automated
- performance bottlenecks are measured, not assumed

Only then should work shift toward:

- PostgreSQL and pgvector hardening
- larger ingestion runs
- ANN index tuning
- batch recomputation jobs
- background workers and operational concerns

## Repository Expectations

To support this model, the repo should gain and maintain:

- a seed data manifest, for example `seed-corpus/manifest.json`
- loader scripts for the development database
- fixture-backed tests that refer to the seed IDs
- UI screenshots or smoke tests generated from the seed corpus
- concise product notes documenting what changed in the user workflow

Current expected local workflow:

- `make seed-corpus-check`
- `make seed-corpus-load`
- `make test-e2e`

## Prioritization Rule

When choosing between two pieces of work:

- prefer the one that improves the end-user workflow on the seed corpus
- defer the one that only prepares for hypothetical scale

That rule should hold unless there is a hard blocker preventing iteration.
