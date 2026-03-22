# ADR-0005: Keep Human-Confirmed And Machine-Applied Labels Distinct

- Status: Accepted
- Date: 2026-03-21

## Context

The system will store face-to-person associations from multiple sources:

- human confirmation
- machine suggestions
- high-confidence machine auto-application

If all of these are treated as equivalent truth, the system risks reinforcing its own mistakes. Machine-applied labels are useful for automation, but they do not have the same reliability as explicit human confirmation.

The product goal is to improve recognition quality over time through user participation while preserving trust and auditability.

## Decision

Store label provenance explicitly and treat human-confirmed labels as the authoritative source of truth.

Machine-generated labels must remain distinct from human-confirmed labels through fields such as:

- `label_source`
- `confidence`
- `model_version`
- timestamps and provenance metadata

Machine-applied labels may be used operationally, but they must not be considered equivalent to human-confirmed labels.

## Consequences

- schema design must include provenance and confidence on face labels or predictions
- recognition and ranking logic must be able to distinguish trusted labels from provisional ones
- the UI should make it easy to review and reverse machine-applied associations
- analytics and evaluation should focus primarily on human-confirmed truth data

## Alternatives Considered

- Treat all labels as equivalent once stored
- Store only final labels and discard provenance
- Disallow all machine-applied labels entirely
