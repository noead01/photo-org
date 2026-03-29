from __future__ import annotations

import os
from typing import Annotated
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, StringConstraints
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
    root_path: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    alias_path: str | None = None
    display_name: str | None = None


class StorageSourceResponse(BaseModel):
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
    metadata_queryable: bool
    thumbnails_available: bool
    originals_available: bool


class IngestRunSummaryResponse(BaseModel):
    status: str
    files_seen: int
    files_created: int
    files_updated: int
    files_missing: int
    error_count: int
    error_summary: str | None = None
    completed_ts: datetime | None = None


class RecentFailureResponse(BaseModel):
    watched_folder_id: str
    status: str
    error_summary: str | None = None
    completed_ts: datetime | None = None


class StorageSourceStatusResponse(StorageSourceResponse):
    alias_paths: list[str]
    watched_folder_count: int
    unreachable_watched_folder_count: int
    catalog: CatalogAvailabilityResponse
    latest_ingest_run: IngestRunSummaryResponse | None = None
    recent_failures: list[RecentFailureResponse]


class CreateWatchedFolderRequest(BaseModel):
    alias_path: str
    watched_path: str
    display_name: str | None = None


class UpdateWatchedFolderRequest(BaseModel):
    is_enabled: bool


class WatchedFolderResponse(BaseModel):
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


@router.get("", response_model=list[StorageSourceStatusResponse])
def list_storage_sources(
    db: Session = Depends(get_db),
) -> list[StorageSourceStatusResponse]:
    rows = list_storage_source_statuses(db.connection())
    return [StorageSourceStatusResponse.model_validate(row) for row in rows]


@router.get(
    "/{storage_source_id}",
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


@router.get("/{storage_source_id}/watched-folders", response_model=list[WatchedFolderResponse])
def list_storage_source_watched_folders(
    storage_source_id: str,
    db: Session = Depends(get_db),
) -> list[WatchedFolderResponse]:
    rows = list_watched_folder_statuses(db.connection(), storage_source_id)
    return [WatchedFolderResponse.model_validate(row) for row in rows]


@router.post(
    "/{storage_source_id}/watched-folders",
    response_model=WatchedFolderResponse,
    status_code=status.HTTP_201_CREATED,
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
    response_model=WatchedFolderResponse,
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
    status_code=status.HTTP_204_NO_CONTENT,
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
