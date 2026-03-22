# ADR-0004: Use Threshold-Based Face Recognition Decisions

- Status: Accepted
- Date: 2026-03-21

## Context

The system should improve its face recognition capability as more faces are labeled, but it must not silently make low-quality identity assignments.

The recognition engine is expected to produce a candidate identity and a confidence score for each detected face. That score can be used to decide whether the system should:

- automatically associate a face with a person
- ask a user to review a suggestion
- leave the face unlabeled

False positive face assignments are significantly more harmful than false negatives in this product. A wrong automatic label can pollute the corpus, damage user trust, and degrade later recognition quality.

## Decision

Use a threshold-based recognition policy with three outcome bands:

- above `auto_accept_threshold`
  - the system may automatically create a machine-applied association
- between `review_threshold` and `auto_accept_threshold`
  - the system should present the association as a suggestion for human confirmation
- below `review_threshold`
  - the system should leave the face unlabeled

Threshold values should be calibrated on a representative seed corpus and not chosen arbitrarily.

## Consequences

- the recognition pipeline must emit confidence scores alongside candidates
- the UI must support review of suggested associations
- the system must retain provenance for automatic and suggested associations
- threshold values become an operationally important configuration that may need tuning over time

## Alternatives Considered

- Require human confirmation for every recognition decision
- Automatically apply the top candidate without thresholds
- Use a binary threshold only, without a separate review band
