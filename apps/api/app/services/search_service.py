from typing import Any, Dict, List
from sqlalchemy import MetaData, Table, select, and_
from sqlalchemy.orm import Session

from app.schemas.search_request import SearchRequest
from app.schemas.search_response import SearchResponse, Hits, PhotoHit
from app.repositories.query_builder import build_base_query, build_filters
from app.repositories.photos_repo import PhotosRepository
from app.services.facets import date_facet, people_facet, tags_facet, duplicates_facet
from app.core.pagination import encode_cursor

class SearchService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PhotosRepository(db)

    def execute(self, req: SearchRequest) -> SearchResponse:
        """ Execute search based on the request and return SearchResponse. """
        md = MetaData()
        bind = self.db.get_bind()  # Session → Engine/Connection

        photos     = Table("photos", md, autoload_with=bind)
        faces      = Table("faces", md, autoload_with=bind)
        photo_tags = Table("photo_tags", md, autoload_with=bind)

        base = build_base_query(photos)
        sel, where_exprs = build_filters(base, photos, faces, photo_tags, req.filters.model_dump(by_alias=True), req.q)

        total = self.repo.count_total(sel)

        order_desc = [photos.c.shot_ts.desc(), photos.c.photo_id.desc()]
        rows = self.repo.select_hits(sel, order_desc, limit=req.page.limit or 50, cursor=req.page.cursor)
        items = self.repo.hydrate_items(rows)

        next_cursor = None
        if items:
            last = items[-1]
            # items already have ISO string, decode to datetime again:
            from datetime import datetime
            next_cursor = encode_cursor(datetime.fromisoformat(last["shot_ts"].replace("Z","+00:00")), last["photo_id"])

        # facet input set (ids of filtered rows ignoring pagination)
        filt_ids = [r.photo_id for r in self.db.execute(select(photos.c.photo_id).where(sel._whereclause) if sel._whereclause is not None else select(photos.c.photo_id)).all()]

        facets = {
            "date": date_facet(self.db, photos, filt_ids),
            "people": people_facet(self.db, faces, filt_ids),
            "tags": tags_facet(self.db, photo_tags, filt_ids),
            "duplicates": duplicates_facet(self.db, photos, filt_ids),
        }

        return SearchResponse(
            hits=Hits(total=total, items=[PhotoHit(**it) for it in items], cursor=next_cursor),
            facets=facets,
        )
