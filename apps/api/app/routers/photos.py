from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.repositories.photos_repo import PhotosRepository
from app.schemas.photo_response import PhotoDetailResponse


router = APIRouter(prefix="/photos", tags=["photos"])


@router.get(
    "/{photo_id}",
    response_model=PhotoDetailResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Photo not found"}},
)
def get_photo_detail(photo_id: str, db: Session = Depends(get_db)) -> PhotoDetailResponse:
    repo = PhotosRepository(db)
    photo = repo.get_photo_detail(photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return PhotoDetailResponse.model_validate(photo)
