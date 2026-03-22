# ADR-0012: Make Observability And Auditability First-Class

- Status: Accepted
- Date: 2026-03-21

## Context

The system has multiple actors:

- admins managing watched folders and configuration
- contributors validating and correcting face associations
- background workers ingesting, reconciling, and classifying photos

These actors perform changes over time that affect:

- catalog contents
- recognition quality
- operational health
- user trust

If the system does not preserve sufficient historical information, users and operators will be unable to answer basic questions such as:

- who changed this label
- why did a photo disappear
- when did a watched folder become unreachable
- what did the background worker do last night

For this product, observability and auditability are not optional operations features. They are part of the user-facing behavior of the system.

## Decision

Treat observability and auditability as first-class architectural requirements.

The system should record and expose historical information for both:

- user-driven actions
- background system actions

At minimum, important actions should capture:

- actor
- action
- target entity
- timestamp
- relevant provenance, reason, or outcome

This expectation should influence:

- schema design
- worker implementation
- admin and contributor UI flows
- API design for historical review and status reporting

## Consequences

- the data model should include explicit run history, status tracking, and action provenance
- background worker behavior should be reviewable after the fact, not only visible in ephemeral logs
- user-facing changes such as label edits should preserve audit history
- admin-facing interfaces should expose operational history and recent system actions
- logs alone are not sufficient as the only historical record

## Alternatives Considered

- Treat observability as an internal logging concern only
- Audit only human user actions and not background system behavior
- Rely on external infrastructure logs without application-level history
