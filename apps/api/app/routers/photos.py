from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.repositories.photos_repo import PhotosRepository
from app.schemas.search_response import PhotoHit


router = APIRouter(prefix="/photos", tags=["photos"])


@router.get("", response_model=list[PhotoHit])
def list_photos(db: Session = Depends(get_db)) -> list[PhotoHit]:
    repo = PhotosRepository(db)
    return [PhotoHit(**item) for item in repo.list_photos()]
