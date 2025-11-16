from typing import Any, Dict, List

from app.schemas.search_request import SearchRequest
from app.schemas.search_response import SearchResponse, Hits, PhotoHit
from app.repositories.photos_repo import PhotosRepository

class SearchService:
    def __init__(self, repo: PhotosRepository):
        self.repo = repo

    def execute(self, req: SearchRequest) -> SearchResponse:
        """Execute search based on the request and return SearchResponse."""
        
        # Use repository for all data access
        items, total, next_cursor = self.repo.search_photos(
            filters=req.filters,
            sort=req.sort,
            page=req.page,
            text_query=req.q
        )

        # Get filtered photo IDs for facet computation
        filtered_photo_ids = self.repo.get_filtered_photo_ids(req.filters, req.q)

        # Compute facets using the repository
        facets = self.repo.compute_facets(filtered_photo_ids)

        return SearchResponse(
            hits=Hits(total=total, items=[PhotoHit(**item) for item in items], cursor=next_cursor),
            facets=facets,
        )
