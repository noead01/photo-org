from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.search_request import SearchRequest
from app.schemas.search_response import SearchResponse
from app.services.search_service import SearchService
from app.repositories.photos_repo import PhotosRepository

router = APIRouter(prefix="/search", tags=["search"])

@router.post("", response_model=SearchResponse)
def search_endpoint(body: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    repo = PhotosRepository(db)
    svc = SearchService(repo=repo)        # Proper DI: inject repository, not database
    return svc.execute(body)
