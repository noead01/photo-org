from __future__ import annotations

from datetime import UTC, datetime
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.storage_source_status import (
    get_storage_source_status,
    list_storage_source_statuses,
    list_watched_folder_statuses,
)
from app.services.source_registration import SourceRegistrationError, register_storage_source
from app.services.watched_folders import (
    WatchedFolderValidationError,
    create_watched_folder,
    remove_watched_folder,
    set_watched_folder_enabled,
)


router = APIRouter(prefix="/storage-sources", tags=["storage-sources"])


class RegisterStorageSourceRequest(BaseModel):
    """Register a storage root that the API can manage and validate."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Register a storage root and optionally bind an alias or display name."
        }
    )

    root_path: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
        Field(description="Absolute path to the storage root on the host."),
    ]
    alias_path: str | None = Field(
        default=None,
        description="Optional canonical alias for the same storage root.",
    )
    display_name: str | None = Field(
        default=None,
        description="Human-readable label shown in the UI and API responses.",
    )


class StorageSourceResponse(BaseModel):
    """Canonical storage-source record returned after registration."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Storage-source identity, marker, and lifecycle metadata."
        }
    )

    storage_source_id: str
    display_name: str
    marker_filename: str
    marker_version: int
    availability_state: str
    last_failure_reason: str | None = None
    last_validated_ts: datetime | None = None
    created_ts: datetime
    updated_ts: datetime


class CatalogAvailabilityResponse(BaseModel):
    """Availability summary for catalog-backed features."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Whether metadata, thumbnails, and originals are available."
        }
    )

    metadata_queryable: bool
    thumbnails_available: bool
    originals_available: bool


class IngestRunSummaryResponse(BaseModel):
    """Summary of the most recent ingest run for a storage source."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Aggregate ingest counts and completion metadata."
        }
    )

    status: str
    files_seen: int
    files_created: int
    files_updated: int
    files_missing: int
    error_count: int
    error_summary: str | None = None
    completed_ts: datetime | None = None


class RecentFailureResponse(BaseModel):
    """Recent watched-folder failures associated with a storage source."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "A compact summary of a watched-folder failure."
        }
    )

    watched_folder_id: str
    status: str
    error_summary: str | None = None
    completed_ts: datetime | None = None


class StorageSourceStatusResponse(StorageSourceResponse):
    """Expanded storage-source state including watched-folder health."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Storage-source registration details plus watched-folder and ingest status."
        }
    )

    alias_paths: list[str]
    watched_folder_count: int
    unreachable_watched_folder_count: int
    catalog: CatalogAvailabilityResponse
    latest_ingest_run: IngestRunSummaryResponse | None = None
    recent_failures: list[RecentFailureResponse]


class CreateWatchedFolderRequest(BaseModel):
    """Create a watched folder relative to a registered storage source."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Register a watched folder beneath a storage-source alias."
        }
    )

    alias_path: str = Field(description="Alias path that identifies the storage source.")
    watched_path: str = Field(description="Path to watch beneath the alias root.")
    display_name: str | None = Field(
        default=None,
        description="Optional label for the watched folder.",
    )


class UpdateWatchedFolderRequest(BaseModel):
    """Toggle whether a watched folder participates in ingest polling."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Enable or disable an existing watched folder."
        }
    )

    is_enabled: bool = Field(description="Whether the watched folder should be active.")


class WatchedFolderResponse(BaseModel):
    """Watched-folder state and recent ingest activity."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Watched-folder identity, status, and last ingest summary."
        }
    )

    watched_folder_id: str
    storage_source_id: str | None = None
    scan_path: str
    relative_path: str | None = None
    display_name: str | None = None
    is_enabled: int
    availability_state: str
    last_failure_reason: str | None = None
    last_successful_scan_ts: datetime | None = None
    latest_ingest_run: IngestRunSummaryResponse | None = None


@router.post(
    "",
    summary="Register storage source",
    description="Create or re-register a storage root that the API manages.",
    response_model=StorageSourceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Storage source registration failed",
        }
    },
)
def register_storage_source_route(body: RegisterStorageSourceRequest) -> StorageSourceResponse:
    try:
        source = register_storage_source(
            database_url=os.getenv("DATABASE_URL"),
            root_path=body.root_path,
            alias_path=body.alias_path,
            display_name=body.display_name,
        )
    except SourceRegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return StorageSourceResponse.model_validate(source)


@router.get(
    "",
    summary="List storage sources",
    description="Return the current storage-source status for all registered roots.",
    response_model=list[StorageSourceStatusResponse],
)
def list_storage_sources(
    db: Session = Depends(get_db),
) -> list[StorageSourceStatusResponse]:
    rows = list_storage_source_statuses(db.connection())
    return [StorageSourceStatusResponse.model_validate(row) for row in rows]


@router.get(
    "/{storage_source_id}",
    summary="Get storage source",
    description="Return the status for a single registered storage source.",
    response_model=StorageSourceStatusResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Storage source not found",
        }
    },
)
def get_storage_source(
    storage_source_id: str,
    db: Session = Depends(get_db),
) -> StorageSourceStatusResponse:
    row = get_storage_source_status(db.connection(), storage_source_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Storage source not found")
    return StorageSourceStatusResponse.model_validate(row)


@router.get(
    "/{storage_source_id}/watched-folders",
    summary="List watched folders",
    description="Return all watched folders attached to a storage source.",
    response_model=list[WatchedFolderResponse],
)
def list_storage_source_watched_folders(
    storage_source_id: str,
    db: Session = Depends(get_db),
) -> list[WatchedFolderResponse]:
    rows = list_watched_folder_statuses(db.connection(), storage_source_id)
    return [WatchedFolderResponse.model_validate(row) for row in rows]


@router.post(
    "/{storage_source_id}/watched-folders",
    summary="Create watched folder",
    description="Create a watched folder for an existing storage source.",
    response_model=WatchedFolderResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Watched folder validation failed",
        }
    },
)
def create_storage_source_watched_folder(
    storage_source_id: str,
    body: CreateWatchedFolderRequest,
    db: Session = Depends(get_db),
) -> WatchedFolderResponse:
    try:
        row = create_watched_folder(
            db.connection(),
            storage_source_id=storage_source_id,
            alias_path=body.alias_path,
            watched_path=body.watched_path,
            display_name=body.display_name,
            now=datetime.now(tz=UTC),
        )
    except WatchedFolderValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return WatchedFolderResponse.model_validate(row)


@router.patch(
    "/{storage_source_id}/watched-folders/{watched_folder_id}",
    summary="Update watched folder",
    description="Enable or disable an existing watched folder.",
    response_model=WatchedFolderResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Watched folder not found",
        }
    },
)
def update_storage_source_watched_folder(
    storage_source_id: str,
    watched_folder_id: str,
    body: UpdateWatchedFolderRequest,
    db: Session = Depends(get_db),
) -> WatchedFolderResponse:
    try:
        row = set_watched_folder_enabled(
            db.connection(),
            storage_source_id=storage_source_id,
            watched_folder_id=watched_folder_id,
            is_enabled=body.is_enabled,
            now=datetime.now(tz=UTC),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return WatchedFolderResponse.model_validate(row)


@router.delete(
    "/{storage_source_id}/watched-folders/{watched_folder_id}",
    summary="Delete watched folder",
    description="Remove a watched folder from the storage source.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Watched folder not found",
        }
    },
)
def delete_storage_source_watched_folder(
    storage_source_id: str,
    watched_folder_id: str,
    db: Session = Depends(get_db),
) -> Response:
    try:
        remove_watched_folder(
            db.connection(),
            storage_source_id=storage_source_id,
            watched_folder_id=watched_folder_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
