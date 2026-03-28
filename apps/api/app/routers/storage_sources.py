from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.watched_folders import (
    WatchedFolderValidationError,
    create_watched_folder,
    list_watched_folders,
    remove_watched_folder,
    set_watched_folder_enabled,
)


router = APIRouter(prefix="/storage-sources", tags=["storage-sources"])


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
    container_mount_path: str
    relative_path: str | None = None
    display_name: str | None = None
    is_enabled: int
    availability_state: str
    last_failure_reason: str | None = None
    last_successful_scan_ts: datetime | None = None


@router.get("/{storage_source_id}/watched-folders", response_model=list[WatchedFolderResponse])
def list_storage_source_watched_folders(
    storage_source_id: str,
    db: Session = Depends(get_db),
) -> list[WatchedFolderResponse]:
    rows = list_watched_folders(db.connection(), storage_source_id)
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
