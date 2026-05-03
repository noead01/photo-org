from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.repositories.photos_repo import PhotosRepository
from app.schemas.photo_response import PhotoDetailResponse
from app.schemas.search_response import PhotoHit


router = APIRouter(prefix="/photos", tags=["photos"])


@router.get(
    "",
    summary="List photos",
    description="Return searchable photo hits from the catalog.",
    response_model=list[PhotoHit],
)
def list_photos(db: Session = Depends(get_db)) -> list[PhotoHit]:
    repo = PhotosRepository(db)
    return [PhotoHit(**item) for item in repo.list_photos()]


@router.get(
    "/{photo_id}",
    summary="Get photo detail",
    description="Return the full photo record, including metadata and availability details.",
    response_model=PhotoDetailResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Photo not found"}},
)
def get_photo_detail(photo_id: str, db: Session = Depends(get_db)) -> PhotoDetailResponse:
    repo = PhotosRepository(db)
    photo = repo.get_photo_detail(photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return PhotoDetailResponse.model_validate(photo)


@router.get(
    "/{photo_id}/original",
    summary="Get photo original",
    description="Stream the original photo file when storage aliases and source markers resolve to a readable file.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Original photo file not found"},
    },
)
def get_photo_original(photo_id: str, db: Session = Depends(get_db)) -> FileResponse:
    repo = PhotosRepository(db)
    resolved = repo.resolve_original_photo_path(photo_id)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original photo not found")

    mime_type, _ = mimetypes.guess_type(str(resolved))
    return FileResponse(
        path=resolved,
        media_type=mime_type or "application/octet-stream",
        filename=resolved.name,
    )
