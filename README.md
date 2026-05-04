# Photo Organizer

Photo Organizer is a local-first web application for families and small groups who want to keep a growing photo library searchable and easier to manage.

It helps you:

- find photos by person, date, and location
- browse and search a shared photo collection from a web browser
- review and confirm detected faces so the system gets more useful over time
- keep a catalog of photos stored in folders you already manage

This README is for users and evaluators of the project. It gives a quick overview of what the system is for, how it is intended to be installed, and how it is used.

For other audiences:

- see [DESIGN.md](DESIGN.md) for architecture, components, and system design
- see [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and contribution standards
- see [docs/adr/README.md](docs/adr/README.md) for architectural decision records

For contributor setup and validation commands, see [CONTRIBUTING.md](CONTRIBUTING.md).

## What It Does

Photo Organizer is intended to support a workflow like this:

1. an admin selects which folders belong to the photo corpus
2. the system watches those folders and ingests new or changed photos
3. users search the collection through a web interface
4. authorized users confirm or correct detected face associations
5. the system becomes more helpful as more faces are validated

Examples of searches the system is meant to support:

- photos of Jane from 2005 to 2007
- photos taken near Paris, France
- photos that include two or more specific people
- photos from a family event or a folder-derived category

## Intended Audience

The primary target is a small group such as a family sharing photos on a local drive or shared network folder and using a web interface on the local network.

The default deployment model is a self-hosted installation on one machine in the home or office network.

## Main Capabilities

- browser-based photo search and browsing
- metadata-based filtering such as date and location
- person-based search using detected and validated faces
- admin management of storage sources and watched folders
- background ingestion of newly added photos
- ingestion status and operational visibility

## Installation Overview

The intended installation model is:

- one host on the local network
- one web UI
- one backend API
- one background worker
- one PostgreSQL database

The preferred packaging model is Docker Compose, and local operation should support multiple named Photo Organizer environments on one machine.
Each local environment is an isolated Compose-managed `postgres` plus `db-service` stack selected with `PHOTO_ORG_ENVIRONMENT=<name>`.
Each environment is created once with an immutable storage mode, either `persistent` or `ephemeral`.

### Prerequisites

- Docker and Docker Compose
- a PostgreSQL database with the `vector` extension enabled
- access from the server to the folders that contain the photo library

The server still needs runtime access to the photo library, but watched-folder registration is now modeled under registered storage sources. Operators should register a source root first, then add watched folders relative to that source boundary instead of treating container mount paths as the user-facing identity contract. Source-backed ingest and reconciliation now derive canonical file identity from the registered storage source plus source-relative paths, not from deployment-specific mount spellings.

If you already have PostgreSQL running separately, the application can use that existing database instead of starting another one.

For PostgreSQL environments managed outside the application stack, a database administrator should enable the extension before running application migrations:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Basic Setup

At a high level, setup should look like this:

1. configure the application environment
2. create an environment with `make env-create PHOTO_ORG_ENVIRONMENT=dev PHOTO_ORG_ENV_STORAGE_MODE=persistent`
3. start it with `PHOTO_ORG_ENVIRONMENT=dev make compose-up`
4. confirm API base URL with `PHOTO_ORG_ENVIRONMENT=dev make print-compose-api-base-url`
5. confirm UI base URL with `PHOTO_ORG_ENVIRONMENT=dev make print-compose-ui-base-url`
6. rerun migrations with `PHOTO_ORG_ENVIRONMENT=dev make compose-migrate` if you need to repair its database
7. open the web interface once the service is healthy
8. sign in as an admin
9. register one or more storage sources through the API at `POST /api/v1/storage-sources`
10. add one or more watched folders under those sources
11. let the system ingest the initial corpus

Once that is done, users should be able to browse, search, and validate faces from the web UI.

For local operations:

- `make env-create PHOTO_ORG_ENVIRONMENT=<name> PHOTO_ORG_ENV_STORAGE_MODE=persistent` registers a persistent environment with its own named Postgres volume
- `make env-create PHOTO_ORG_ENVIRONMENT=<name> PHOTO_ORG_ENV_STORAGE_MODE=ephemeral` registers an ephemeral environment whose database lives only for the container lifecycle
- `PHOTO_ORG_ENVIRONMENT=<name> make compose-up` starts the selected registered environment (API + database + web UI)
- `PHOTO_ORG_ENVIRONMENT=<name> make compose-down` removes containers while preserving a persistent environment's named Postgres volume
- `PHOTO_ORG_ENVIRONMENT=<name> make compose-down-volumes` removes containers and deletes a persistent environment's local Postgres volume
- `PHOTO_ORG_ENVIRONMENT=<name> make compose-smoke` verifies the selected environment using its registered storage mode
- `make compose-e2e-smoke` creates a random ephemeral environment, runs `compose-smoke`, runs the checked-in e2e suite against that environment's Compose database, and tears it down automatically
- `PHOTO_ORG_ENVIRONMENT=<name> make print-compose-api-base-url` prints the API URL for that environment
- `PHOTO_ORG_ENVIRONMENT=<name> make print-compose-ui-base-url` prints the UI URL for that environment
- `PHOTO_ORG_ENV_FILE=/path/to/file.env` can be added when you want a local command to load extra environment-specific settings
- `PHOTO_ORG_ENVIRONMENT=<name> PHOTO_ORG_ENV_FILE=env/presets/face-detection-high-precision.env make compose-up` starts the selected environment with the named `high_precision` face-detection profile

The default Compose file now bind-mounts `${PHOTO_ORG_PHOTO_LIBRARY_HOST_PATH}` into `${PHOTO_ORG_PHOTO_LIBRARY_CONTAINER_PATH}` for `db-service`, defaulting to `./seed-corpus` mounted at `/photos`. It also bind-mounts `${PHOTO_ORG_MODEL_HOST_PATH}` into `${PHOTO_ORG_MODEL_CONTAINER_PATH}`, defaulting to `/mnt/d/models` mounted at `/models` for ONNX model artifacts. That runtime mount remains an internal deployment concern; watched-folder registration should stay relative to a registered source root.

The API allows cross-origin browser calls from the configured UI host origins through `PHOTO_ORG_API_CORS_ALLOWED_ORIGINS` (comma-separated origins).

## Basic Usage

Typical usage is expected to be:

- admin users register sources through `POST /api/v1/storage-sources`, then add, remove, or disable watched folders under those sources
- the system ingests new photos in the background
- users search for photos by person, date, and location
- suggestion workflows can fetch nearest labeled candidates with `GET /api/v1/faces/{face_id}/candidates`; when policy resolves to `auto_apply` and the source face is still unlabeled, the API auto-assigns the top candidate, records a `machine_applied` label event (including `model_version` plus prediction provenance), and returns `auto_applied_assignment`; when policy resolves to `review_needed`, the API records a `machine_suggested` label event with the same metadata and returns `review_needed_suggestion` for human confirmation
- authorized users confirm or correct face associations
- users monitor ingestion status and recent issues from the UI

Recognition suggestion behavior is configurable through environment variables:

- `PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD` (default `0.7`)
- `PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD` (default `0.9`)
- `PHOTO_ORG_RECOGNITION_MODEL_VERSION` (default `nearest-neighbor-cosine-v1`)

Face detection behavior is configurable through environment variables:

- `FACE_DETECT_PROFILE` (default `balanced`) with built-in profiles:
  - `balanced`
  - `high_precision`
  - `high_recall`
  - `portraits`
- `FACE_DETECT_PROFILE_FILE` (optional path to JSON profile definitions; defaults to `apps/api/app/processing/face_detect_profiles.json`)
- `FACE_DETECT_SCALE_FACTOR` (default `1.1`)
- `FACE_DETECT_MIN_NEIGHBORS` (default `5`)
- `FACE_DETECT_MIN_SIZE` (default `60x60`)
- `FACE_DETECT_MAX_SIZE` (optional, example `420x420`)
- `FACE_DETECT_MIN_AREA_RATIO` (default `0.0`)
- `FACE_DETECT_MAX_AREA_RATIO` (default `1.0`)
- `FACE_DETECT_ASPECT_RATIO_MIN` (default `0.0`)
- `FACE_DETECT_ASPECT_RATIO_MAX` (default `100.0`)
- `FACE_RECOGNITION_SFACE_MODEL_FILE` (default `/models/opencv/face_recognition_sface_2021dec.onnx`; set empty to disable embedding extraction)

Preset files are checked in under `env/presets/` (each includes a full parameter set):

- `face-detection-balanced.env`
- `face-detection-high-precision.env`
- `face-detection-high-recall.env`
- `face-detection-portraits.env`

When both `FACE_DETECT_PROFILE` and specific `FACE_DETECT_*` variables are set, explicit `FACE_DETECT_*` variables override the selected profile values.

For operator troubleshooting during long imports or background processing, the API exposes two operational endpoints:

- `GET /api/v1/operations/activity` for a live snapshot of active polling and ingest work
- `GET /api/v1/operations/activity/history` for completed and failed operational history

The live endpoint is read-only and intended for repeated polling by a UI or CLI. It shows only work that is currently underway. The history endpoint is separate so completed and failed activity can be reviewed without being conflated with current live state.

## Current Documentation

- [DESIGN.md](DESIGN.md): how the system is structured and how components interact
- [CONTRIBUTING.md](CONTRIBUTING.md): contribution and development workflow standards
- [ROADMAP.md](ROADMAP.md): prioritized feature roadmap and implementation sequence
- [docs/adr/README.md](docs/adr/README.md): architectural decisions and rationale
- [docs/ITERATIVE_DEVELOPMENT.md](docs/ITERATIVE_DEVELOPMENT.md): phased development approach for the project

## Status

The project is still being shaped and documented. The architecture, operational model, and development standards are being defined before the main implementation is expanded.

The current Phase 0 development path now uses an API-owned persistence boundary for ingest work:

- `poll-storage-sources` now performs discovery and candidate scheduling only
- queued workers hash content and, when needed, run metadata extraction, thumbnail generation, and face detection before persistence
- duplicate-content files reuse existing extracted artifacts by SHA instead of re-running full analysis
- the API owns queue processing and domain-table mutation
- internal polling and queue processing can be triggered through bounded API endpoints for worker use

The API publishes its code-defined OpenAPI contract as JSON at `/openapi.json`, YAML at `/openapi.yaml`, and Swagger UI at `/docs`.

The repository also now includes a checked-in offline seed corpus for end-to-end validation and demos:

- the corpus lives under `seed-corpus/`
- assets are curated for deterministic ingest and search behavior
- source and license metadata are tracked in `seed-corpus/manifest.json`
- contributor workflows for validating and loading the corpus are documented in [CONTRIBUTING.md](CONTRIBUTING.md)

For contributor-facing details about that boundary, see [CONTRIBUTING.md](CONTRIBUTING.md) and ADR-0013 in [docs/adr/README.md](docs/adr/README.md).
