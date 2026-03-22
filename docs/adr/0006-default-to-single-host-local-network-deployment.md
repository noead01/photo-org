# ADR-0006: Default To Single-Host Local-Network Deployment

- Status: Accepted
- Date: 2026-03-21

## Context

The target user group is a small group such as a family sharing photos on a shared drive and using a web interface from devices on the same local network.

The system should be easy to install and operate without requiring cloud infrastructure, distributed systems expertise, or complex operational tooling.

The product needs:

- a web UI
- an API
- a background ingestion service
- PostgreSQL with `pgvector`

These components could be deployed in many ways, but the default deployment model should optimize for simplicity of installation, operation, and backup.

## Decision

Adopt a single-host local-network deployment model as the default installation target.

The preferred packaging should be Docker Compose with the main services running on one host:

- UI
- API
- background worker
- PostgreSQL

Redis should remain optional and only be introduced when justified by concrete operational needs.

The worker should access the photo corpus through host-mounted folders or host-mounted shared drives rather than requiring photos to be copied into an application-specific store.

## Consequences

- the system should be designed to operate well with all core services on one machine
- installation and upgrade flows should prioritize Docker Compose simplicity
- admin workflows should assume watched folders are configured through the web UI
- local-network-only security defaults are appropriate for the initial product
- advanced deployment patterns such as public internet exposure, reverse proxies, and multi-host scaling become secondary modes rather than the default

## Alternatives Considered

- Default to a cloud-hosted deployment
- Default to a multi-host distributed architecture
- Require per-user desktop installs instead of a shared web application
