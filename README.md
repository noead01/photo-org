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
- admin management of watched folders
- background ingestion of newly added photos
- ingestion status and operational visibility

## Installation Overview

The intended installation model is:

- one host on the local network
- one web UI
- one backend API
- one background worker
- one PostgreSQL database

The preferred packaging model is Docker Compose.

### Prerequisites

- Docker and Docker Compose
- a PostgreSQL database with the `vector` extension enabled
- access from the server to the folders that contain the photo library

If you already have PostgreSQL running separately, the application can use that existing database instead of starting another one.

## Basic Setup

At a high level, setup should look like this:

1. configure the application environment
2. start the application stack
3. open the web interface
4. sign in as an admin
5. add one or more watched folders
6. let the system ingest the initial corpus

Once that is done, users should be able to browse, search, and validate faces from the web UI.

## Basic Usage

Typical usage is expected to be:

- admin users add, remove, or disable watched folders
- the system ingests new photos in the background
- users search for photos by person, date, and location
- authorized users confirm or correct face associations
- users monitor ingestion status and recent issues from the UI

## Current Documentation

- [DESIGN.md](DESIGN.md): how the system is structured and how components interact
- [CONTRIBUTING.md](CONTRIBUTING.md): contribution and development workflow standards
- [ROADMAP.md](ROADMAP.md): prioritized feature roadmap and implementation sequence
- [docs/adr/README.md](docs/adr/README.md): architectural decisions and rationale
- [docs/ITERATIVE_DEVELOPMENT.md](docs/ITERATIVE_DEVELOPMENT.md): phased development approach for the project

## Status

The project is still being shaped and documented. The architecture, operational model, and development standards are being defined before the main implementation is expanded.
