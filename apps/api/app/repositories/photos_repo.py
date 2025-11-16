from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import MetaData, Table, select, func, or_, and_, text
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.schemas.search_request import SearchFilters, SortSpec, PageSpec
from app.core.enums import FilesizeRange


class PhotosRepository:
    def __init__(self, db: Session):
        self.db = db
        bind = db.get_bind()
        md = MetaData()
        # Single source of truth for table objects
        self.photos: Table = Table("photos", md, autoload_with=bind)
        self.faces: Table = Table("faces", md, autoload_with=bind)
        self.photo_tags: Table = Table("photo_tags", md, autoload_with=bind)

    def search_photos(self, filters: SearchFilters, sort: SortSpec, page: PageSpec, 
                     text_query: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
        """
        Main search method that handles all query building and execution.
        Returns: (items, total_count, next_cursor)
        """
        # Build the complete query
        query = self._build_search_query(filters, text_query)
        
        # Get total count before pagination
        total_count = self._count_total(query)
        
        # Apply sorting and pagination (pagination needs sort info)
        query = self._apply_sorting(query, sort)
        query = self._apply_pagination(query, page, sort)
        
        # Execute query
        rows = list(self.db.execute(query).all())
        
        # Hydrate results with related data
        items = self._hydrate_items(rows)
        
        # Generate next cursor
        next_cursor = self._generate_cursor(items, sort) if items else None
        
        return items, total_count, next_cursor

    def get_filtered_photo_ids(self, filters: SearchFilters, text_query: Optional[str] = None) -> List[str]:
        """Get photo IDs for facet computation."""
        query = select(self.photos.c.photo_id)
        query = self._apply_filters(query, filters, text_query)
        return [row.photo_id for row in self.db.execute(query).all()]

    def _build_search_query(self, filters: SearchFilters, text_query: Optional[str] = None) -> Select:
        """Build the base search query with all columns."""
        query = select(
            self.photos.c.photo_id, self.photos.c.path, self.photos.c.ext, 
            self.photos.c.camera_make, self.photos.c.orientation, self.photos.c.shot_ts, 
            self.photos.c.filesize, self.photos.c.sha256, self.photos.c.phash
        )
        return self._apply_filters(query, filters, text_query)

    def _apply_filters(self, query: Select, filters: SearchFilters, text_query: Optional[str] = None) -> Select:
        """Apply all filters to the query."""
        where_conditions = []
        
        # Date filters
        if filters.date:
            if filters.date.from_:
                where_conditions.append(self.photos.c.shot_ts >= text(f"'{filters.date.from_}T00:00:00Z'"))
            if filters.date.to:
                where_conditions.append(self.photos.c.shot_ts <= text(f"'{filters.date.to}T23:59:59Z'"))
        
        # Simple list filters
        if filters.camera_make:
            where_conditions.append(self.photos.c.camera_make.in_(filters.camera_make))
        if filters.extension:
            where_conditions.append(self.photos.c.ext.in_(filters.extension))
        if filters.orientation:
            where_conditions.append(self.photos.c.orientation.in_(filters.orientation))
        
        # Filesize range filter
        if filters.filesize_range:
            lo, hi = filters.filesize_range.bounds()
            where_conditions.append(and_(self.photos.c.filesize >= lo, self.photos.c.filesize < hi))
        
        # Has faces filter
        if filters.has_faces is True:
            faces_subquery = select(self.faces.c.photo_id).where(
                self.faces.c.photo_id == self.photos.c.photo_id
            ).limit(1)
            where_conditions.append(faces_subquery.exists())
        
        # People filter (OR logic within people)
        if filters.people:
            people_subquery = select(self.faces.c.photo_id).where(
                and_(
                    self.faces.c.photo_id == self.photos.c.photo_id,
                    self.faces.c.person_id.in_(filters.people)
                )
            ).limit(1)
            where_conditions.append(people_subquery.exists())
        
        # Tags filter (OR logic within tags)
        if filters.tags:
            tags_subquery = select(self.photo_tags.c.photo_id).where(
                and_(
                    self.photo_tags.c.photo_id == self.photos.c.photo_id,
                    self.photo_tags.c.tag.in_(filters.tags)
                )
            ).limit(1)
            where_conditions.append(tags_subquery.exists())
        
        # Text query filter
        if text_query:
            tokens = [t for t in text_query.lower().split() if t]
            if tokens:
                tag_exists = select(self.photo_tags.c.photo_id).where(
                    (self.photo_tags.c.photo_id == self.photos.c.photo_id) &
                    or_(*[self.photo_tags.c.tag.ilike(f"%{t}%") for t in tokens])
                ).limit(1).exists()
                where_conditions.append(or_(
                    self.photos.c.path.ilike(f"%{tokens[0]}%"), 
                    tag_exists
                ))
        
        if where_conditions:
            query = query.where(and_(*where_conditions))
        
        return query

    def _apply_sorting(self, query: Select, sort: SortSpec) -> Select:
        """Apply sorting to the query."""
        if sort.by == "shot_ts":
            if sort.dir == "desc":
                return query.order_by(self.photos.c.shot_ts.desc(), self.photos.c.photo_id.desc())
            else:
                return query.order_by(self.photos.c.shot_ts.asc(), self.photos.c.photo_id.asc())
        elif sort.by == "relevance":
            # For now, fallback to shot_ts sorting
            # TODO: Implement actual relevance scoring
            return query.order_by(self.photos.c.shot_ts.desc(), self.photos.c.photo_id.desc())
        else:
            return query.order_by(self.photos.c.shot_ts.desc(), self.photos.c.photo_id.desc())

    def _apply_pagination(self, query: Select, page: PageSpec, sort: SortSpec) -> Select:
        """Apply pagination to the query."""
        if page.cursor:
            from app.core.pagination import decode_cursor
            last_ts, last_pid = decode_cursor(page.cursor)
            
            # Cursor conditions depend on sort direction
            if sort.dir == "desc":
                # For descending: next page has timestamps < last_ts
                query = query.where(or_(
                    self.photos.c.shot_ts < last_ts,
                    and_(self.photos.c.shot_ts == last_ts, self.photos.c.photo_id < last_pid)
                ))
            else:  # asc
                # For ascending: next page has timestamps > last_ts
                query = query.where(or_(
                    self.photos.c.shot_ts > last_ts,
                    and_(self.photos.c.shot_ts == last_ts, self.photos.c.photo_id > last_pid)
                ))
        
        limit = page.limit or 50
        return query.limit(limit)

    def _count_total(self, query: Select) -> int:
        """Count total results for a query."""
        count_query = select(func.count()).select_from(query.subquery())
        return int(self.db.execute(count_query).scalar_one())

    def _generate_cursor(self, items: List[Dict[str, Any]], sort: SortSpec) -> Optional[str]:
        """Generate cursor for next page."""
        if not items:
            return None
        
        last_item = items[-1]
        from datetime import datetime
        from app.core.pagination import encode_cursor
        
        # Convert ISO string back to datetime for cursor encoding
        shot_ts_str = last_item["shot_ts"]
        shot_ts_dt = datetime.fromisoformat(shot_ts_str.replace("Z", "+00:00"))
        
        return encode_cursor(shot_ts_dt, last_item["photo_id"])

    def _hydrate_items(self, rows: List[Row]) -> List[Dict[str, Any]]:
        """Hydrate photo rows with related data (tags, people, faces)."""
        if not rows:
            return []
        
        pids = [r.photo_id for r in rows]

        # Build lookup maps for related data
        tag_map = {pid: [] for pid in pids}
        ppl_map = {pid: [] for pid in pids}
        faces_map = {pid: [] for pid in pids}

        # Load tags
        for r in self.db.execute(
            select(self.photo_tags.c.photo_id, self.photo_tags.c.tag)
            .where(self.photo_tags.c.photo_id.in_(pids))
        ).all():
            tag_map[r.photo_id].append(r.tag)

        # Load faces and people
        for r in self.db.execute(
            select(self.faces.c.photo_id, self.faces.c.person_id)
            .where(self.faces.c.photo_id.in_(pids))
        ).all():
            if r.person_id:
                ppl_map[r.photo_id].append(r.person_id)
            faces_map[r.photo_id].append({"person_id": r.person_id})

        # Build final result items
        from app.core.pagination import iso_utc
        return [
            {
                "photo_id": r.photo_id,
                "path": r.path,
                "ext": (r.ext or "").lower(),
                "camera_make": r.camera_make,
                "orientation": r.orientation,
                "shot_ts": iso_utc(r.shot_ts),
                "filesize": int(r.filesize or 0),
                "tags": tag_map.get(r.photo_id, []),
                "people": ppl_map.get(r.photo_id, []),
                "faces": faces_map.get(r.photo_id, []),
            }
            for r in rows
        ]

    # Legacy methods for backward compatibility (can be removed after refactoring)
    def select_hits(self, sel, order_desc, limit: int, cursor: str | None) -> List[Row]:
        """Legacy method - deprecated, use search_photos instead."""
        from app.core.pagination import decode_cursor
        sel = sel.order_by(*order_desc)
        if cursor:
            last_ts, last_pid = decode_cursor(cursor)
            sel = sel.where(or_(self.photos.c.shot_ts < last_ts,
                                and_(self.photos.c.shot_ts == last_ts,
                                     self.photos.c.photo_id < last_pid)))
        return list(self.db.execute(sel.limit(limit)).all())

    def count_total(self, sel) -> int:
        """Legacy method - deprecated, use search_photos instead."""
        return int(self.db.execute(select(func.count()).select_from(sel.subquery())).scalar_one())

    def hydrate_items(self, rows: List[Row]) -> List[Dict[str, Any]]:
        """Legacy method - deprecated, use search_photos instead."""
        return self._hydrate_items(rows)

    def compute_facets(self, filtered_photo_ids: List[str]) -> Dict[str, Any]:
        """Compute facets for the filtered photo set."""
        # Import both old and new facet systems
        from app.services.facets import date_facet, people_facet, duplicates_facet
        from app.domain.facets import TagsFacet, FacetContext
        
        # Use new domain model for tags facet
        tags_facet_instance = TagsFacet()
        context = FacetContext(
            db=self.db,
            photo_tags=self.photo_tags,
            faces=self.faces,
            photos=self.photos
        )
        
        # Compute tags using new domain model
        tags_result = tags_facet_instance.compute(filtered_photo_ids, context)
        tags_formatted = [{"value": v.value, "count": v.count} for v in tags_result.values]
        
        return {
            "date": date_facet(self.db, self.photos, filtered_photo_ids),
            "people": people_facet(self.db, self.faces, filtered_photo_ids),
            "tags": tags_formatted,  # Using new domain model
            "duplicates": duplicates_facet(self.db, self.photos, filtered_photo_ids),
        }
