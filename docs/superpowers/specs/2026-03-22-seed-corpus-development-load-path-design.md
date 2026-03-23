# Seed Corpus Development Load Path Design

## Context

Issue `#19` covers the Phase 0 requirement to establish a repeatable seed-corpus development path that supports real end-to-end validation and demos.

The current repository has two useful but incomplete fixture surfaces:

- synthetic seeded database rows for fast search and BDD-style tests
- a small set of sample photo files for ingest metadata extraction

Those fixtures are intentionally narrow. They do not provide one representative, stable corpus that the full system can ingest end to end for repeatable validation of real workflows.

The project documentation already points toward a deliberately small development corpus:

- `ROADMAP.md` calls for a repeatable seed-corpus development load path in Foundations
- `docs/ITERATIVE_DEVELOPMENT.md` centers Phase 0 and later product decisions on a fixed seed corpus

This issue is intentionally about the corpus asset and its integration path. It should not replace the synthetic fixtures used by unit or BDD coverage, and it should not attempt to build every future end-to-end test in one change.

## Decision

Implement issue `#19` by checking a small, offline seed corpus directly into the main repository under a dedicated root-level directory.

The initial implementation should:

- store the actual photo files in the repo so the corpus is available offline
- organize the files into predefined folders and subfolders that exercise representative scenarios
- keep the corpus intentionally small and curated rather than comprehensive
- allow curated metadata adjustments so the dataset remains predictable for validation
- define a machine-readable manifest that downstream tooling and tests can rely on deterministically
- use the corpus as a stable asset for authoritative end-to-end suites and demos

Synthetic fixtures remain the preferred source for unit tests and BDD scenarios.

## Design

### Corpus Ownership And Location

The corpus should live in one explicitly owned root-level directory such as `seed-corpus/`.

Keeping the files in the main repository is the simplest way to preserve:

- offline repeatability
- fixed folder layout
- stable metadata expectations
- easy local setup for contributors and demos

The repository should treat this directory as a product-development fixture, not as user content and not as a general-purpose sample dump.

### Corpus Composition

The corpus should be small enough to keep repository growth controlled while still representing the real workflows the product needs to validate.

The target shape is approximately:

- 20 to 50 photos
- multiple file formats such as `jpg`, `jpeg`, `png`, and `heic` where practical
- multiple nested folders and subfolders
- a mix of photos with and without EXIF metadata
- a mix of photos with recognizable faces and photos with no faces
- enough variety to support ingest, face-label, and search scenarios

The files do not need to originate from one source. They may be curated from public internet sources or derived assets, but included photos should be free of copyright restrictions or otherwise clearly licensed for redistribution in the repository. Once included they become repo-owned fixtures with stable paths and stable expected traits.

### Scenario Coverage

The corpus should be intentionally designed around representative end-to-end scenarios rather than assembled opportunistically.

At minimum it should support:

- ingesting a nested folder tree
- extracting metadata from mixed-format files
- handling missing or incomplete metadata without collapsing the workflow
- detecting at least a few recognizable faces for later labeling workflows
- validating named-face scenarios after labels are applied
- exercising basic search and browse scenarios on stable photo identities

The corpus may also include a few deliberately useful edge cases such as:

- duplicate or near-duplicate photos
- inconsistent camera metadata
- photos with location metadata and photos without it
- multiple people in one image

### Metadata Control

The corpus is allowed to contain curated or artificially adjusted metadata when that is necessary to create predictable test behavior.

That includes:

- normalized filenames or paths
- edited EXIF fields
- known timestamps
- controlled GPS values
- predictable face-bearing images for labeling scenarios

The priority is determinism, not archival purity. The dataset exists to make workflows observable and testable.

### Asset Licensing

The corpus should be assembled only from assets that are safe to redistribute in the repository.

That means:

- prefer public-domain or equivalently unrestricted images
- allow other included assets only when their licenses clearly permit redistribution in-repo
- record source and license information in the manifest or adjacent corpus documentation
- avoid relying on "publicly accessible" images whose copyright or redistribution status is unclear

This licensing constraint should apply even when an image would otherwise be a strong scenario fit. Predictable test data is necessary, but legally clean test data is mandatory.

### Manifest Contract

The repository should include a machine-readable manifest for the corpus, stored alongside the corpus or in a nearby dedicated metadata file.

The manifest should describe each asset with enough structure for validation and end-to-end tests to rely on known expectations. Each entry should include at least:

- stable asset identifier
- relative file path
- expected file format
- scenario tags or categories
- notable metadata expectations such as presence or absence of timestamp, GPS, or camera fields
- whether a face-bearing image is expected to participate in face-label scenarios

The manifest is not just documentation. It is the contract between the corpus and the tooling that validates or exercises it.

### Workflow Boundary

Issue `#19` should add one documented local workflow that prepares the system to run against the checked-in corpus.

That workflow should:

- validate the corpus contents and manifest
- run the existing ingest path against the corpus root
- trigger or invoke the required API-side processing path
- leave the system in a state where end-to-end tests or demos can operate on the loaded dataset

This workflow should be exposed through one stable contributor-facing command path, preferably via the existing `Makefile` or a small wrapper script under `scripts/`.

### Verification Boundary

The corpus itself is not the source of truth for behavior. The end-to-end suite is.

The intended contract is:

- synthetic fixtures remain the preferred source for unit and BDD coverage
- the checked-in corpus becomes the stable asset used by automated end-to-end validation suites
- the end-to-end suite becomes the authoritative verification surface for implemented system behavior on real files

Issue `#19` should therefore establish two verification layers:

1. corpus integrity checks
2. initial end-to-end suite integration using the corpus as fixed input data

Corpus integrity checks should verify:

- expected files exist
- manifest entries match the filesystem layout
- declared formats and notable traits are internally consistent

Initial end-to-end integration should prove:

- the system can ingest the corpus repeatably
- the loaded dataset is stable enough for later feature assertions
- downstream e2e tests can refer to known corpus assets without ad hoc discovery

### Scope For Issue #19

Issue `#19` should include:

- a root-level checked-in seed corpus
- a deterministic manifest
- validation tooling for corpus integrity
- one documented local load path
- an initial e2e integration slice that uses the corpus

It should not include:

- replacing synthetic test fixtures across the repo
- downloading the corpus from the network as the primary workflow
- building every future end-to-end scenario in this issue
- expanding the dataset beyond a deliberately small development corpus

## Verification

Verification for issue `#19` should focus on repeatability and e2e readiness:

- automated checks for manifest and filesystem consistency
- a documented local workflow that loads the checked-in corpus without network fetches
- at least one end-to-end suite path that ingests the corpus and asserts representative expected outcomes
- contributor-facing documentation explaining how the corpus is intended to be used versus synthetic fixtures

## Outcome

After issue `#19`:

- the repository contains one offline, curated seed corpus with stable layout and expectations
- contributors can prepare a repeatable local dataset for demos and end-to-end validation without ad hoc setup
- unit and BDD coverage remain fast and synthetic
- end-to-end suites gain a fixed real-file dataset that can serve as the behavioral source of truth for implemented workflows
