# Architecture Decision Records

## Purpose

This directory contains Architecture Decision Records (ADRs) for the project.

Each ADR captures:

- the decision being made
- the context that made the decision necessary
- the chosen option
- the consequences of that choice

## Naming

Use the format:

- `0001-short-title.md`
- `0002-another-title.md`

Numbers should be sequential and never reused.

## Status Values

Use one of:

- `Proposed`
- `Accepted`
- `Superseded`
- `Deprecated`

If an ADR is replaced, keep the old one and mark it `Superseded` with a reference to the newer ADR.

## Template

Use this structure:

```md
# ADR-XXXX: Title

- Status: Proposed
- Date: YYYY-MM-DD

## Context

What problem are we solving? What constraints matter?

## Decision

What are we deciding?

## Consequences

What becomes easier, harder, or required because of this decision?

## Alternatives Considered

- Option A
- Option B
```

## Scope

ADRs should be used for decisions that affect one or more of:

- system architecture
- service boundaries
- schema design
- storage technologies
- background processing model
- external dependencies
- operational model

Do not create ADRs for minor implementation details unless they constrain the architecture.
