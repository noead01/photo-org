# Phase 3 Search Scenario Catalog Design

## Summary

Phase 3 should not start by designing a transport-specific search API or by guessing at a query DSL in the abstract. It should start by defining a curated catalog of realistic search intents, expressed in natural language, then validating that each intent can be normalized into a canonical search contract.

This scenario catalog is the critical-path design artifact for Phase 3. It is intended to drive:

- the canonical search DSL and its semantics
- Phase 3 implementation ordering and acceptance criteria
- future NLP translation work
- seed-corpus enrichment for search validation

## Goals

- Define a meaningful set of search scenarios that represent how users are likely to search the catalog.
- Classify each scenario by current scope, future ambition, and expected DSL support level.
- Use the scenario set to shape a transport-agnostic canonical search contract.
- Identify data gaps in the current seed corpus that block realistic search validation.
- Provide a stable source for future automated tests and manual demo scripts.

## Non-Goals

- This document does not finalize the JSON shape or field names of the Phase 3 search DSL.
- This document does not choose REST or GraphQL as the runtime transport.
- This document does not implement NLP translation.
- This document does not require all future-looking scenarios to be executable in Phase 3.

## Why The Scenario Catalog Comes First

Search contracts become brittle when they are designed around current columns instead of user intent. The project already has a partial search code path, but that code path should not become the de facto contract. The contract should instead be derived from realistic search scenarios that can be normalized consistently.

This order of operations keeps the system honest:

1. capture user intent in natural language
2. define intended meaning precisely
3. normalize that meaning into a canonical query form
4. decide which scenarios Phase 3 must support, which should reserve shape for later, and which should be rejected explicitly

## Scenario Entry Format

Each search scenario should be recorded with the following fields:

- `id`: stable identifier such as `S01`
- `group`: scenario family
- `natural_language`: the user-facing phrasing
- `intent`: plain-English meaning after ambiguity is resolved
- `phase_scope`: `phase_3`, `future`, or `out_of_scope`
- `dsl_status`: `supported_now`, `reserved_shape`, or `intentionally_unsupported`
- `canonical_query`: transport-agnostic normalized form
- `expected_behavior`: what matching and result behavior should mean
- `seed_corpus_requirements`: current coverage or required additions
- `notes`: ambiguity, assumptions, or future hooks

## Classification Rules

### `phase_scope`

- `phase_3`: the scenario should be executable and validated during Phase 3
- `future`: the scenario should influence DSL shape now, but execution can wait for later phases or data improvements
- `out_of_scope`: the scenario is useful as a boundary case and should be rejected cleanly if attempted

### `dsl_status`

- `supported_now`: the canonical search contract should represent and execute the scenario in Phase 3
- `reserved_shape`: the canonical contract should represent the scenario now even if execution is deferred
- `intentionally_unsupported`: the canonical contract should not silently approximate this scenario

## Normalization Rules

The scenario catalog should enforce the following normalization rules on the future DSL:

- The canonical contract expresses meaning, not transport syntax.
- Equivalent intents should normalize to the same structure.
- Filter families combine with explicit `AND` semantics unless documented otherwise.
- Multi-value filters must define whether they mean `ANY`, `ALL`, or another operator.
- Person filters reference stable person identifiers, not raw display-name strings.
- Location filters use typed spatial predicates rather than free-text guessing.
- Pagination is cursor-based and stable under a documented sort order.
- When sorting by `shot_ts`, null timestamps sort last in both directions, with `photo_id` as the deterministic tie-breaker among rows with the same timestamp state.
- Unsupported intents fail clearly instead of degrading into vague text search.

## Canonical Query Shape

The catalog uses a transport-agnostic pseudo-structure to describe normalized search requests:

```text
query:
  text:
    terms: [...]
    fields: [...]
  filters:
    date_range: { from, to }
    people_any: [...]
    has_faces: true|false
    extension_any: [...]
    tags_any: [...]
    path_hints_any: [...]
    camera_make_any: [...]
    location_radius: { latitude, longitude, radius_km }
  facets: [...]
  sort: { by, direction }
  page: { limit, cursor }
```

This pseudo-structure is descriptive only. The actual DSL can use different field names if it preserves the same semantics.

## Scenario Groups

The initial catalog is organized into eight groups:

- text discovery
- date and time filtering
- people filtering
- location and proximity
- facet exploration
- combined multi-clause search
- deterministic sorting and pagination
- future-boundary scenarios

## Initial Scenario Catalog

### Text Discovery

| ID | Natural Language | Scope | DSL | Canonical Query | Expected Behavior | Seed Corpus Requirements |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | "photos matching lake" | `phase_3` | `supported_now` | `text: {terms: ["lake"], fields: ["path", "tags"]}` | Match photos whose indexed path hints or tags include `lake`. | Existing seed corpus already contains `lake-weekend` paths. |
| S02 | "Canon photos" | `phase_3` | `supported_now` | `filters: {camera_make_any: ["Canon"]}` | Match photos with `camera_make=Canon`. | Existing metadata appears sufficient. |
| S03 | "jpeg photos from the trip folder" | `phase_3` | `supported_now` | `filters: {extension_any: ["jpeg"], path_hints_any: ["travel"]}` | Combine file-extension and path-hint filtering with `AND`. | Existing paths include `travel/city-break`. |

### Date And Time Filtering

| ID | Natural Language | Scope | DSL | Canonical Query | Expected Behavior | Seed Corpus Requirements |
| --- | --- | --- | --- | --- | --- | --- |
| S04 | "photos from July 2022" | `phase_3` | `supported_now` | `filters: {date_range: {from: "2022-07-01", to: "2022-07-31"}}` | Inclusive date-range filtering on canonical shot timestamp. | Existing seed corpus contains July photos. |
| S05 | "photos before the birthday weekend" | `future` | `reserved_shape` | `filters: {date_range: {to: "2022-06-13"}}` | Relative language should normalize externally to an absolute date before execution. | Needs scenario metadata narrative, not new DSL features. |
| S06 | "oldest birthday photos first" | `phase_3` | `supported_now` | `filters: {path_hints_any: ["birthday-park"]}, sort: {by: "shot_ts", direction: "asc"}` | Deterministic ascending order with null handling documented. | Existing seed corpus supports this. |

### People Filtering

| ID | Natural Language | Scope | DSL | Canonical Query | Expected Behavior | Seed Corpus Requirements |
| --- | --- | --- | --- | --- | --- | --- |
| S07 | "photos of person_ines" | `phase_3` | `supported_now` | `filters: {people_any: ["person_ines"]}` | Match any photo with at least one face linked to `person_ines`. | Needs seed corpus with stable person IDs in fixtures. |
| S08 | "photos of Jane or Ines" | `phase_3` | `supported_now` | `filters: {people_any: ["person_jane", "person_ines"]}` | `ANY` semantics within the people filter. | Requires at least two labeled identities. |
| S09 | "photos of Jane and Ines together" | `future` | `reserved_shape` | `filters: {people_all: ["person_jane", "person_ines"]}` | Require all listed people to appear in the same photo. | Needs multi-person labeled photos. |
| S10 | "photos with faces but nobody identified yet" | `future` | `reserved_shape` | `filters: {has_faces: true, people_none: true}` | Match photos with detected faces and no assigned people. | Depends on labeling workflow and unlabeled-face data. |

### Location And Proximity

| ID | Natural Language | Scope | DSL | Canonical Query | Expected Behavior | Seed Corpus Requirements |
| --- | --- | --- | --- | --- | --- | --- |
| S11 | "photos taken near Paris" | `future` | `reserved_shape` | `filters: {location_radius: {latitude: 48.8566, longitude: 2.3522, radius_km: 10}}` | Typed radius filter over canonical GPS coordinates. | Seed corpus needs realistic geotagged samples. |
| S12 | "photos within 5 km of this point" | `phase_3` | `supported_now` | `filters: {location_radius: {latitude: <lat>, longitude: <lon>, radius_km: 5}}` | Coordinate-based proximity is the minimum viable Phase 3 geo predicate and should not require place-name geocoding in the DSL. | Needs geotagged fixtures and UI/runtime source for coordinates. |
| S13 | "photos in France" | `out_of_scope` | `intentionally_unsupported` | none | Geographic region inference should not be guessed by the core DSL. | Would require reverse geocoding or region metadata. |

### Facet Exploration

| ID | Natural Language | Scope | DSL | Canonical Query | Expected Behavior | Seed Corpus Requirements |
| --- | --- | --- | --- | --- | --- | --- |
| S14 | "show me the available people filters for lake weekend photos" | `phase_3` | `supported_now` | `filters: {path_hints_any: ["lake-weekend"]}, facets: ["people"]` | Compute people facet values over the filtered result set. | Needs labeled people to be meaningful. |
| S15 | "show me monthly counts for 2022 photos" | `phase_3` | `supported_now` | `filters: {date_range: {from: "2022-01-01", to: "2022-12-31"}}, facets: ["date"]` | Return date hierarchy or equivalent facet structure. | Existing timestamps are sufficient. |
| S16 | "show me face-bearing vs no-face photos for travel pictures" | `future` | `reserved_shape` | `filters: {path_hints_any: ["travel"]}, facets: ["has_faces"]` | Facet-style boolean breakdown should be available for filtered sets. | Requires explicit `has_faces` facet support. |

### Combined Multi-Clause Search

| ID | Natural Language | Scope | DSL | Canonical Query | Expected Behavior | Seed Corpus Requirements |
| --- | --- | --- | --- | --- | --- | --- |
| S17 | "Canon photos from July 2022 with faces" | `phase_3` | `supported_now` | `filters: {camera_make_any: ["Canon"], date_range: {from: "2022-07-01", to: "2022-07-31"}, has_faces: true}` | Combine unrelated filters with `AND`. | Existing metadata likely supports this. |
| S18 | "birthday photos with no faces" | `phase_3` | `supported_now` | `filters: {path_hints_any: ["birthday-park"], has_faces: false}` | Explicitly support `has_faces=false`, not just `true`. | Existing seed corpus appears to contain both variants. |
| S19 | "photos of person_ines from summer 2022" | `future` | `reserved_shape` | `filters: {people_any: ["person_ines"], date_range: {from: "2022-06-01", to: "2022-08-31"}}` | Represents a common person-plus-time slice. | Needs stable person labels through Phase 4 data. |
| S20 | "lake weekend photos sorted by newest first" | `phase_3` | `supported_now` | `filters: {path_hints_any: ["lake-weekend"]}, sort: {by: "shot_ts", direction: "desc"}` | Deterministic ordering over a filtered subset. | Already supported by seed corpus structure. |

### Deterministic Sorting And Pagination

| ID | Natural Language | Scope | DSL | Canonical Query | Expected Behavior | Seed Corpus Requirements |
| --- | --- | --- | --- | --- | --- | --- |
| S21 | "show me the first 5 newest photos" | `phase_3` | `supported_now` | `sort: {by: "shot_ts", direction: "desc"}, page: {limit: 5}` | First page is stable and reproducible. | Existing corpus sufficient. |
| S22 | "give me the next page of that result" | `phase_3` | `supported_now` | `sort: {by: "shot_ts", direction: "desc"}, page: {limit: 5, cursor: "<cursor>"}` | Cursor traversal must not reorder or duplicate items. | Existing corpus sufficient. |
| S23 | "show photos without shot timestamps last" | `phase_3` | `supported_now` | `sort: {by: "shot_ts", direction: "desc"}` | Null timestamp handling is part of documented sort semantics. | Existing tests already cover null timestamp behavior. |

### Future-Boundary Scenarios

| ID | Natural Language | Scope | DSL | Canonical Query | Expected Behavior | Seed Corpus Requirements |
| --- | --- | --- | --- | --- | --- | --- |
| S24 | "photos of Jane from 2005 to 2007 near Paris" | `future` | `reserved_shape` | `filters: {people_any: ["person_jane"], date_range: {from: "2005-01-01", to: "2007-12-31"}, location_radius: {latitude: 48.8566, longitude: 2.3522, radius_km: 10}}` | Representative long-term aspiration: typed people, time, and location composition. | Needs person labels plus realistic geo/date coverage. |
| S25 | "photos where Jane and Ines appear together during summer trips near the lake" | `future` | `reserved_shape` | `filters: {people_all: ["person_jane", "person_ines"], date_range: {from: "2022-06-01", to: "2022-08-31"}, path_hints_any: ["lake", "travel"]}` | Demonstrates future `ALL` people semantics plus mixed filters. | Needs multi-person labeled travel scenarios. |
| S26 | "find visually similar photos to this face crop" | `out_of_scope` | `intentionally_unsupported` | none | This belongs to recognition and similarity workflows, not the Phase 3 search DSL. | Later phases may add vector search through a separate query family. |
| S27 | "show photos from the party where Jane looked happy" | `out_of_scope` | `intentionally_unsupported` | none | Mood or semantic-scene inference should not be guessed by the search contract. | Would require separate ML labeling capabilities. |

## What The Initial Catalog Implies About The DSL

The initial scenario set implies the future canonical search contract needs:

- text search as a distinct clause, not as a fallback for every unsupported filter
- inclusive date-range filtering over canonical shot timestamps
- typed multi-value filters with explicit operator semantics
- explicit boolean filtering for `has_faces`
- path-derived hints as a first-class searchable/filterable signal
- typed spatial predicates for future proximity work
- typed spatial predicates for Phase 3 coordinate-based proximity work and later higher-level location adapters
- facet requests over the filtered result set
- stable sort and cursor pagination semantics independent of transport

It also implies that the canonical contract should reserve room for:

- `people_all`
- `people_none`
- future boolean facets such as `has_faces`
- future geo predicates

## Seed Corpus Follow-Up

The current seed corpus is already strong enough to validate many Phase 3 scenarios around:

- path-derived hints
- event-like folder groupings
- date range filtering
- deterministic ordering
- face-bearing versus no-face photos
- camera metadata

The main gaps exposed by the scenario catalog are:

- stable person-linked scenarios meaningful enough for search validation
- geotagged scenarios for proximity search
- multi-person scenarios that make `people_all` meaningful
- scenarios with unlabeled but detected faces

These gaps should inform future corpus supplementation rather than being worked around in the DSL.

## Recommended Next Actions

1. Treat this scenario catalog as the prerequisite input to the Phase 3 search DSL design.
2. Add a new foundational Phase 3 issue under parent issue `#10` for defining the canonical search contract from the scenario catalog.
3. Reframe issue `#40` so it derives executable validation fixtures from the approved scenario set.
4. Keep NLP out of Phase 3 implementation scope, but require future NLP work to normalize into the canonical contract defined from this catalog.

## Verification

This is a design artifact. Its correctness should be checked by:

- internal consistency review against the Phase 3 goals in `ROADMAP.md`
- review of whether each `phase_3` scenario is realistic for the seed-corpus-driven product
- confirmation that future scenarios reserve shape without forcing premature implementation
