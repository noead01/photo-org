import base64
import json
import math
import posixpath
from datetime import UTC, datetime, time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import MetaData, Table, select, func, or_, and_, case
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.path_contract import normalize_relative_path
from app.schemas.search_request import SearchFilters, SortSpec, PageSpec
from app.domain.facets import (
    TagsFacet,
    PeopleFacet,
    HasFacesFacet,
    DateHierarchyFacet,
    DuplicatesFacet,
    FacetContext,
    FacetResult,
    FacetValue,
)
from app.core.pagination import iso_utc


def _coerce_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value.is_integer():
        parsed = int(value)
        return parsed if parsed > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = int(text)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def _extract_bbox_space_dimensions(face_provenance: object) -> tuple[int | None, int | None]:
    if not isinstance(face_provenance, dict):
        return (None, None)

    width = _coerce_positive_int(face_provenance.get("bbox_space_width"))
    height = _coerce_positive_int(face_provenance.get("bbox_space_height"))
    return (width, height)


class PhotosRepository:
    def __init__(self, db: Session):
        self.db = db
        bind = db.get_bind()
        md = MetaData()
        # Single source of truth for table objects
        self.photos: Table = Table("photos", md, autoload_with=bind)
        self.faces: Table = Table("faces", md, autoload_with=bind)
        self.people: Table = Table("people", md, autoload_with=bind)
        self.photo_tags: Table = Table("photo_tags", md, autoload_with=bind)
        self.face_labels: Table = Table("face_labels", md, autoload_with=bind)
        self.face_suggestions: Table = Table("face_suggestions", md, autoload_with=bind)
        self.photo_files: Table = Table("photo_files", md, autoload_with=bind)
        self.photo_exif_attributes: Table = Table("photo_exif_attributes", md, autoload_with=bind)
        self.exif_semantic_mappings: Table = Table("exif_semantic_mappings", md, autoload_with=bind)
        self.watched_folders: Table = Table("watched_folders", md, autoload_with=bind)
        self.storage_sources: Table = Table("storage_sources", md, autoload_with=bind)
        self.storage_source_aliases: Table = Table("storage_source_aliases", md, autoload_with=bind)

    @staticmethod
    def _normalize_person_name_terms(person_names: List[str]) -> List[str]:
        terms = []
        for name in person_names:
            term = name.strip()
            if term:
                terms.append(term)
        return terms

    @staticmethod
    def _escape_like_literal(term: str) -> str:
        return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _suggestion_confidence_threshold(filters: SearchFilters) -> float:
        return float(filters.suggestion_confidence_min) if filters.suggestion_confidence_min is not None else 0.0

    def _build_people_filter_clause(self, filters: SearchFilters):
        person_ids = filters.people or []
        if not person_ids:
            return None

        person_certainty_mode = filters.person_certainty_mode
        if person_certainty_mode is None:
            people_subquery = select(self.faces.c.photo_id).where(
                and_(
                    self.faces.c.photo_id == self.photos.c.photo_id,
                    self.faces.c.person_id.in_(person_ids),
                )
            ).limit(1)
            return people_subquery.exists()

        confirmed_match_exists = (
            select(self.faces.c.photo_id)
            .select_from(
                self.faces.join(
                    self.face_labels,
                    and_(
                        self.face_labels.c.face_id == self.faces.c.face_id,
                        self.face_labels.c.person_id == self.faces.c.person_id,
                    ),
                )
            )
            .where(
                and_(
                    self.faces.c.photo_id == self.photos.c.photo_id,
                    self.face_labels.c.person_id.in_(person_ids),
                    self.face_labels.c.label_source == "human_confirmed",
                )
            )
            .limit(1)
            .exists()
        )

        if person_certainty_mode == "human_only":
            return confirmed_match_exists

        if person_certainty_mode == "include_suggestions":
            suggestion_match_exists = (
                select(self.faces.c.photo_id)
                .select_from(
                    self.faces.join(
                        self.face_suggestions,
                        self.face_suggestions.c.face_id == self.faces.c.face_id,
                    )
                )
                .where(
                    and_(
                        self.faces.c.photo_id == self.photos.c.photo_id,
                        self.face_suggestions.c.person_id.in_(person_ids),
                        self.face_suggestions.c.confidence >= self._suggestion_confidence_threshold(filters),
                    )
                )
                .limit(1)
                .exists()
            )
            return or_(confirmed_match_exists, suggestion_match_exists)

        return None

    def _build_person_name_filter_clause(self, filters: SearchFilters):
        person_name_terms = self._normalize_person_name_terms(filters.person_names or [])
        if not person_name_terms:
            return None

        person_name_predicate = or_(
            *[
                self.people.c.display_name.ilike(
                    f"%{self._escape_like_literal(name)}%",
                    escape="\\",
                )
                for name in person_name_terms
            ]
        )

        person_certainty_mode = filters.person_certainty_mode
        if person_certainty_mode is None:
            person_name_subquery = (
                select(self.faces.c.photo_id)
                .select_from(
                    self.faces.join(
                        self.people,
                        self.faces.c.person_id == self.people.c.person_id,
                    )
                )
                .where(
                    and_(
                        self.faces.c.photo_id == self.photos.c.photo_id,
                        person_name_predicate,
                    )
                )
                .limit(1)
            )
            return person_name_subquery.exists()

        confirmed_match_exists = (
            select(self.faces.c.photo_id)
            .select_from(
                self.faces.join(
                    self.people,
                    self.faces.c.person_id == self.people.c.person_id,
                ).join(
                    self.face_labels,
                    and_(
                        self.face_labels.c.face_id == self.faces.c.face_id,
                        self.face_labels.c.person_id == self.faces.c.person_id,
                    ),
                )
            )
            .where(
                and_(
                    self.faces.c.photo_id == self.photos.c.photo_id,
                    self.face_labels.c.label_source == "human_confirmed",
                    person_name_predicate,
                )
            )
            .limit(1)
            .exists()
        )

        if person_certainty_mode == "human_only":
            return confirmed_match_exists

        if person_certainty_mode == "include_suggestions":
            suggestion_match_exists = (
                select(self.faces.c.photo_id)
                .select_from(
                    self.faces.join(
                        self.face_suggestions,
                        self.face_suggestions.c.face_id == self.faces.c.face_id,
                    ).join(
                        self.people,
                        self.face_suggestions.c.person_id == self.people.c.person_id,
                    )
                )
                .where(
                    and_(
                        self.faces.c.photo_id == self.photos.c.photo_id,
                        self.face_suggestions.c.confidence >= self._suggestion_confidence_threshold(filters),
                        person_name_predicate,
                    )
                )
                .limit(1)
                .exists()
            )
            return or_(confirmed_match_exists, suggestion_match_exists)

        return None

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

    def get_photo_detail(self, photo_id: str) -> Optional[Dict[str, Any]]:
        query = select(
            self.photos.c.photo_id,
            self.photos.c.path,
            self.photos.c.ext,
            self.photos.c.camera_make,
            self.photos.c.camera_model,
            self.photos.c.software,
            self.photos.c.orientation,
            self.photos.c.shot_ts,
            self.photos.c.shot_ts_source,
            self.photos.c.filesize,
            self.photos.c.sha256,
            self.photos.c.phash,
            self.photos.c.gps_latitude,
            self.photos.c.gps_longitude,
            self.photos.c.gps_altitude,
            self.photos.c.thumbnail_jpeg,
            self.photos.c.thumbnail_mime_type,
            self.photos.c.thumbnail_width,
            self.photos.c.thumbnail_height,
            self.photos.c.created_ts,
            self.photos.c.updated_ts,
            self.photos.c.modified_ts,
            self.photos.c.deleted_ts,
            self.photos.c.faces_count,
            self.photos.c.faces_detected_ts,
        ).where(
            self.photos.c.photo_id == photo_id,
            self.photos.c.deleted_ts.is_(None),
        )

        rows = list(self.db.execute(query).all())
        if not rows:
            return None

        item = self._hydrate_items(rows, include_face_regions=True)[0]
        row = rows[0]
        exif_attributes = self._load_photo_exif_attributes(photo_id)
        exif_unmapped_attributes = self._load_photo_exif_unmapped_attributes(photo_id)
        item["metadata"] = {
            "sha256": row.sha256,
            "phash": row.phash,
            "shot_ts_source": self._normalize_shot_ts_source_label(
                row.shot_ts_source,
                exif_attributes=exif_attributes,
            ),
            "camera_model": row.camera_model,
            "software": row.software,
            "gps_latitude": row.gps_latitude,
            "gps_longitude": row.gps_longitude,
            "gps_altitude": row.gps_altitude,
            "exif_attributes": exif_attributes,
            "exif_unmapped_attributes": exif_unmapped_attributes,
            "created_ts": row.created_ts,
            "updated_ts": row.updated_ts,
            "modified_ts": row.modified_ts,
            "deleted_ts": row.deleted_ts,
            "faces_count": int(row.faces_count or 0),
            "faces_detected_ts": row.faces_detected_ts,
        }
        return item

    @staticmethod
    def _normalize_shot_ts_source_label(
        shot_ts_source: str | None,
        *,
        exif_attributes: dict[str, object] | None,
    ) -> str | None:
        if shot_ts_source is None:
            return None

        if shot_ts_source.startswith("exif_attr:"):
            legacy_source = shot_ts_source.removeprefix("exif_attr:")
            if legacy_source.startswith("exif_ifd.") or legacy_source.startswith("exif."):
                namespace, tag_name = legacy_source.split(".", 1)
                return f"{namespace}:{tag_name}"

        if shot_ts_source == "exif:DateTimeOriginal" and exif_attributes:
            has_ifd_original = "exif_ifd.DateTimeOriginal" in exif_attributes
            has_exif_original = "exif.DateTimeOriginal" in exif_attributes
            if has_ifd_original and not has_exif_original:
                return "exif_ifd:DateTimeOriginal"

        return shot_ts_source

    def _load_photo_exif_attributes(self, photo_id: str) -> dict[str, object] | None:
        rows = self.db.execute(
            select(
                self.photo_exif_attributes.c.exif_attribute_name,
                self.photo_exif_attributes.c.exif_attribute_value,
            )
            .where(self.photo_exif_attributes.c.photo_id == photo_id)
            .order_by(self.photo_exif_attributes.c.exif_attribute_name.asc())
        ).all()
        if not rows:
            return None
        return {row.exif_attribute_name: row.exif_attribute_value for row in rows}

    def _load_photo_exif_unmapped_attributes(self, photo_id: str) -> dict[str, object] | None:
        rows = self.db.execute(
            select(
                self.photo_exif_attributes.c.exif_attribute_name,
                self.photo_exif_attributes.c.exif_attribute_value,
            )
            .select_from(
                self.photo_exif_attributes.outerjoin(
                    self.exif_semantic_mappings,
                    self.photo_exif_attributes.c.exif_attribute_name
                    == self.exif_semantic_mappings.c.exif_attribute_name,
                )
            )
            .where(self.photo_exif_attributes.c.photo_id == photo_id)
            .where(self.exif_semantic_mappings.c.exif_attribute_name.is_(None))
            .order_by(self.photo_exif_attributes.c.exif_attribute_name.asc())
        ).all()
        if not rows:
            return None
        return {row.exif_attribute_name: row.exif_attribute_value for row in rows}

    def list_photos(self) -> List[Dict[str, Any]]:
        """Return catalog photos in a deterministic browse order."""
        query = select(self.photos).order_by(*self._sorting_clauses(SortSpec()))
        rows = [row for row in self.db.execute(query).all() if row.deleted_ts is None]
        return self._hydrate_items(rows)

    def resolve_original_photo_path(self, photo_id: str) -> Optional[Path]:
        rows = self.db.execute(
            select(
                self.photo_files.c.relative_path,
                self.photo_files.c.last_seen_ts,
                self.photo_files.c.created_ts,
                self.photo_files.c.photo_file_id,
                self.watched_folders.c.scan_path,
                self.watched_folders.c.relative_path.label("watched_folder_relative_path"),
                self.watched_folders.c.storage_source_id,
                self.storage_sources.c.marker_filename,
            )
            .select_from(
                self.photo_files.outerjoin(
                    self.watched_folders,
                    self.photo_files.c.watched_folder_id == self.watched_folders.c.watched_folder_id,
                ).outerjoin(
                    self.storage_sources,
                    self.watched_folders.c.storage_source_id == self.storage_sources.c.storage_source_id,
                )
            )
            .where(self.photo_files.c.photo_id == photo_id)
            .where(self.photo_files.c.deleted_ts.is_(None))
            .where(self.photo_files.c.lifecycle_state == "active")
            .order_by(
                self.photo_files.c.last_seen_ts.desc(),
                self.photo_files.c.created_ts.desc(),
                self.photo_files.c.photo_file_id.desc(),
            )
        ).mappings().all()

        for row in rows:
            photo_relative_path = self._normalize_relative_path_or_none(row["relative_path"])
            if photo_relative_path is None:
                continue

            storage_source_id = row["storage_source_id"]
            if storage_source_id:
                resolved = self._resolve_registered_storage_source_file(
                    storage_source_id=str(storage_source_id),
                    marker_filename=str(row["marker_filename"] or ".photo-org-source.json"),
                    watched_folder_relative_path=row["watched_folder_relative_path"],
                    photo_relative_path=photo_relative_path,
                )
                if resolved is not None:
                    return resolved
                continue

            scan_path = row["scan_path"]
            if not isinstance(scan_path, str) or not scan_path.strip():
                continue

            try:
                scan_root = Path(scan_path).expanduser().resolve()
            except OSError:
                continue

            candidate = self._resolve_candidate_path(scan_root, photo_relative_path)
            if candidate is not None:
                return candidate

        return None

    def _resolve_registered_storage_source_file(
        self,
        *,
        storage_source_id: str,
        marker_filename: str,
        watched_folder_relative_path: object,
        photo_relative_path: str,
    ) -> Optional[Path]:
        alias_rows = self.db.execute(
            select(self.storage_source_aliases.c.alias_path)
            .where(self.storage_source_aliases.c.storage_source_id == storage_source_id)
            .order_by(self.storage_source_aliases.c.alias_path)
        ).all()
        watched_relative = self._normalize_relative_path_or_none(watched_folder_relative_path)
        source_relative = self._join_relative_paths(watched_relative, photo_relative_path)
        if source_relative is None:
            return None

        for alias_row in alias_rows:
            alias_path = alias_row.alias_path
            if not isinstance(alias_path, str) or not alias_path.strip():
                continue
            try:
                alias_root = Path(alias_path).expanduser().resolve()
            except OSError:
                continue

            if not self._is_storage_source_marker_valid(
                alias_root=alias_root,
                storage_source_id=storage_source_id,
                marker_filename=marker_filename,
            ):
                continue

            candidate = self._resolve_candidate_path(alias_root, source_relative)
            if candidate is not None:
                return candidate

        return None

    @staticmethod
    def _is_storage_source_marker_valid(
        *,
        alias_root: Path,
        storage_source_id: str,
        marker_filename: str,
    ) -> bool:
        marker_path = alias_root / marker_filename
        if not marker_path.is_file():
            return False

        try:
            marker_payload = json.loads(marker_path.read_text())
        except (OSError, json.JSONDecodeError):
            return False

        if not isinstance(marker_payload, dict):
            return False

        return str(marker_payload.get("storage_source_id")) == storage_source_id

    @staticmethod
    def _normalize_relative_path_or_none(value: object) -> Optional[str]:
        if not isinstance(value, str):
            return None

        raw = value.strip()
        if raw in {"", "."}:
            return None

        try:
            return normalize_relative_path(raw)
        except ValueError:
            return None

    @staticmethod
    def _join_relative_paths(left: Optional[str], right: str) -> Optional[str]:
        if left is None:
            return right

        joined = posixpath.normpath(posixpath.join(left, right))
        try:
            return normalize_relative_path(joined)
        except ValueError:
            return None

    @staticmethod
    def _resolve_candidate_path(root: Path, relative_path: str) -> Optional[Path]:
        try:
            candidate = (root / relative_path).resolve()
        except OSError:
            return None

        try:
            candidate.relative_to(root)
        except ValueError:
            return None

        if not candidate.is_file():
            return None

        return candidate

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
            self.photos.c.filesize, self.photos.c.sha256, self.photos.c.phash,
            self.photos.c.thumbnail_jpeg, self.photos.c.thumbnail_mime_type,
            self.photos.c.thumbnail_width, self.photos.c.thumbnail_height,
        )
        return self._apply_filters(query, filters, text_query)

    def _apply_filters(self, query: Select, filters: SearchFilters, text_query: Optional[str] = None) -> Select:
        """Apply all filters to the query."""
        where_conditions = [self.photos.c.deleted_ts.is_(None)]
        
        # Date filters
        if filters.date:
            if filters.date.from_:
                from_bound = datetime.combine(
                    datetime.fromisoformat(filters.date.from_).date(),
                    time.min,
                    tzinfo=UTC,
                )
                where_conditions.append(self.photos.c.shot_ts >= from_bound)
            if filters.date.to:
                to_bound = datetime.combine(
                    datetime.fromisoformat(filters.date.to).date(),
                    time.max,
                    tzinfo=UTC,
                )
                where_conditions.append(self.photos.c.shot_ts <= to_bound)
        
        # Simple list filters
        if filters.camera_make:
            where_conditions.append(self.photos.c.camera_make.in_(filters.camera_make))
        if filters.extension:
            where_conditions.append(self.photos.c.ext.in_(filters.extension))
        if filters.path_hints:
            where_conditions.append(
                or_(*[self.photos.c.path.ilike(f"%{hint}%") for hint in filters.path_hints])
            )
        if filters.orientation:
            where_conditions.append(self.photos.c.orientation.in_(filters.orientation))

        if filters.location_radius:
            latitude = filters.location_radius.latitude
            longitude = filters.location_radius.longitude
            radius_km = filters.location_radius.radius_km

            earth_radius_km = 6371.0088
            degrees_to_radians = math.pi / 180.0
            latitude_radians = latitude * degrees_to_radians
            longitude_radians = longitude * degrees_to_radians
            photo_latitude_radians = self.photos.c.gps_latitude * degrees_to_radians
            photo_longitude_radians = self.photos.c.gps_longitude * degrees_to_radians

            cosine_distance = (
                func.sin(latitude_radians) * func.sin(photo_latitude_radians)
                + func.cos(latitude_radians)
                * func.cos(photo_latitude_radians)
                * func.cos(photo_longitude_radians - longitude_radians)
            )
            clamped_cosine_distance = case(
                (cosine_distance > 1.0, 1.0),
                (cosine_distance < -1.0, -1.0),
                else_=cosine_distance,
            )
            spherical_distance_km = earth_radius_km * func.acos(clamped_cosine_distance)

            where_conditions.append(
                and_(
                    self.photos.c.gps_latitude.is_not(None),
                    self.photos.c.gps_longitude.is_not(None),
                    spherical_distance_km <= radius_km,
                )
            )
        
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
        elif filters.has_faces is False:
            faces_subquery = select(self.faces.c.photo_id).where(
                self.faces.c.photo_id == self.photos.c.photo_id
            ).limit(1)
            where_conditions.append(~faces_subquery.exists())
        
        people_clause = self._build_people_filter_clause(filters)
        if people_clause is not None:
            where_conditions.append(people_clause)

        person_name_clause = self._build_person_name_filter_clause(filters)
        if person_name_clause is not None:
            where_conditions.append(person_name_clause)
        
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
                token_conditions = []
                for token in tokens:
                    tag_exists = (
                        select(self.photo_tags.c.photo_id)
                        .where(
                            and_(
                                self.photo_tags.c.photo_id == self.photos.c.photo_id,
                                self.photo_tags.c.tag.ilike(f"%{token}%"),
                            )
                        )
                        .limit(1)
                        .exists()
                    )
                    token_conditions.append(
                        or_(
                            self.photos.c.path.ilike(f"%{token}%"),
                            tag_exists,
                        )
                    )
                where_conditions.append(and_(*token_conditions))
        
        if where_conditions:
            query = query.where(and_(*where_conditions))
        
        return query

    def _apply_sorting(self, query: Select, sort: SortSpec) -> Select:
        """Apply sorting to the query."""
        return query.order_by(*self._sorting_clauses(sort))

    def _apply_pagination(self, query: Select, page: PageSpec, sort: SortSpec) -> Select:
        """Apply pagination to the query."""
        if page.cursor:
            from app.core.pagination import decode_cursor
            last_ts, last_pid = decode_cursor(page.cursor)

            query = query.where(self._cursor_boundary_clause(last_ts, last_pid, sort))
        
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
        shot_ts_dt = None if shot_ts_str is None else datetime.fromisoformat(shot_ts_str.replace("Z", "+00:00"))
        
        return encode_cursor(shot_ts_dt, last_item["photo_id"])

    def _sorting_clauses(self, sort: SortSpec):
        """Return a deterministic sort order with null timestamps last."""
        direction = sort.dir if sort.by in {"shot_ts", "relevance"} else "desc"
        shot_ts_order = self.photos.c.shot_ts.desc() if direction == "desc" else self.photos.c.shot_ts.asc()
        photo_id_order = self.photos.c.photo_id.desc() if direction == "desc" else self.photos.c.photo_id.asc()
        return (
            self.photos.c.shot_ts.is_(None),
            shot_ts_order,
            photo_id_order,
        )

    def _cursor_boundary_clause(self, last_ts: Optional[datetime], last_pid: str, sort: SortSpec):
        """Return the strict boundary for the next page in the current sort order."""
        direction = sort.dir if sort.by in {"shot_ts", "relevance"} else "desc"

        if last_ts is None:
            pid_clause = self.photos.c.photo_id < last_pid if direction == "desc" else self.photos.c.photo_id > last_pid
            return and_(self.photos.c.shot_ts.is_(None), pid_clause)

        ts_clause = self.photos.c.shot_ts < last_ts if direction == "desc" else self.photos.c.shot_ts > last_ts
        pid_clause = self.photos.c.photo_id < last_pid if direction == "desc" else self.photos.c.photo_id > last_pid
        return or_(
            and_(
                self.photos.c.shot_ts.is_not(None),
                or_(
                    ts_clause,
                    and_(self.photos.c.shot_ts == last_ts, pid_clause),
                ),
            ),
            self.photos.c.shot_ts.is_(None),
        )

    def _hydrate_items(self, rows: List[Row], *, include_face_regions: bool = False) -> List[Dict[str, Any]]:
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
        face_columns = [self.faces.c.photo_id, self.faces.c.face_id, self.faces.c.person_id]
        if include_face_regions:
            face_columns.extend(
                [
                    self.faces.c.bbox_x,
                    self.faces.c.bbox_y,
                    self.faces.c.bbox_w,
                    self.faces.c.bbox_h,
                    self.faces.c.provenance,
                ]
            )

        face_rows = self.db.execute(
            select(*face_columns)
            .where(self.faces.c.photo_id.in_(pids))
            .order_by(self.faces.c.photo_id, self.faces.c.face_id)
        ).all()
        face_ids = sorted({str(r.face_id) for r in face_rows if r.face_id is not None})

        provenance_map: Dict[tuple[str, str], Dict[str, Any]] = {}
        labeled_face_keys = {
            (str(r.face_id), str(r.person_id))
            for r in face_rows
            if r.person_id is not None and r.face_id is not None
        }
        if labeled_face_keys:
            face_ids = sorted({face_id for face_id, _ in labeled_face_keys})
            label_rows = (
                self.db.execute(
                    select(
                        self.face_labels.c.face_id,
                        self.face_labels.c.person_id,
                        self.face_labels.c.label_source,
                        self.face_labels.c.confidence,
                        self.face_labels.c.model_version,
                        self.face_labels.c.provenance,
                        self.face_labels.c.created_ts,
                        self.face_labels.c.updated_ts,
                        self.face_labels.c.face_label_id,
                    )
                    .where(self.face_labels.c.face_id.in_(face_ids))
                    .order_by(
                        self.face_labels.c.face_id,
                        self.face_labels.c.person_id,
                        self.face_labels.c.updated_ts.desc(),
                        self.face_labels.c.created_ts.desc(),
                        self.face_labels.c.face_label_id.desc(),
                    )
                )
                .mappings()
                .all()
            )
            for row in label_rows:
                person_id = row["person_id"]
                face_id = row["face_id"]
                if person_id is None or face_id is None:
                    continue
                key = (str(face_id), str(person_id))
                if key not in labeled_face_keys or key in provenance_map:
                    continue
                provenance_map[key] = {
                    "label_source": row["label_source"],
                    "confidence": row["confidence"],
                    "model_version": row["model_version"],
                    "provenance": row["provenance"],
                    "label_recorded_ts": (
                        iso_utc(row["updated_ts"])
                        if row["updated_ts"] is not None
                        else (iso_utc(row["created_ts"]) if row["created_ts"] is not None else None)
                    ),
                }

        suggestion_map: Dict[str, List[Dict[str, Any]]] = {face_id: [] for face_id in face_ids}
        if face_ids:
            suggestion_rows = (
                self.db.execute(
                    select(
                        self.face_suggestions.c.face_id,
                        self.face_suggestions.c.person_id,
                        self.people.c.display_name,
                        self.face_suggestions.c.rank,
                        self.face_suggestions.c.confidence,
                        self.face_suggestions.c.model_version,
                        self.face_suggestions.c.provenance,
                    )
                    .select_from(
                        self.face_suggestions.join(
                            self.people,
                            self.face_suggestions.c.person_id == self.people.c.person_id,
                        )
                    )
                    .where(self.face_suggestions.c.face_id.in_(face_ids))
                    .order_by(
                        self.face_suggestions.c.face_id.asc(),
                        self.face_suggestions.c.rank.asc(),
                        self.face_suggestions.c.person_id.asc(),
                    )
                )
                .mappings()
                .all()
            )
            for row in suggestion_rows:
                suggestion_map.setdefault(str(row["face_id"]), []).append(
                    {
                        "person_id": str(row["person_id"]),
                        "display_name": str(row["display_name"]),
                        "rank": int(row["rank"]),
                        "confidence": float(row["confidence"]),
                        "model_version": row["model_version"],
                        "provenance": row["provenance"],
                    }
                )

        for r in face_rows:
            if r.person_id:
                ppl_map[r.photo_id].append(r.person_id)
            provenance = (
                provenance_map.get((str(r.face_id), str(r.person_id)))
                if r.person_id is not None and r.face_id is not None
                else None
            )
            face_item = {
                "person_id": r.person_id,
                "label_source": provenance["label_source"] if provenance else None,
                "confidence": provenance["confidence"] if provenance else None,
                "suggestions": suggestion_map.get(str(r.face_id), []),
            }
            if include_face_regions:
                bbox_space_width, bbox_space_height = _extract_bbox_space_dimensions(r.provenance)
                face_item.update(
                    {
                        "face_id": r.face_id,
                        "bbox_x": r.bbox_x,
                        "bbox_y": r.bbox_y,
                        "bbox_w": r.bbox_w,
                        "bbox_h": r.bbox_h,
                        "bbox_space_width": bbox_space_width,
                        "bbox_space_height": bbox_space_height,
                        "label_source": provenance["label_source"] if provenance else None,
                        "confidence": provenance["confidence"] if provenance else None,
                        "model_version": provenance["model_version"] if provenance else None,
                        "provenance": provenance["provenance"] if provenance else None,
                        "label_recorded_ts": provenance["label_recorded_ts"] if provenance else None,
                        "suggestions": suggestion_map.get(str(r.face_id), []),
                    }
                )
            faces_map[r.photo_id].append(face_item)

        original_map = self._load_original_availability(pids)

        # Build final result items
        return [
            {
                "photo_id": r.photo_id,
                "path": r.path,
                "ext": (r.ext or "").lower(),
                "camera_make": r.camera_make,
                "orientation": r.orientation,
                "shot_ts": iso_utc(r.shot_ts) if r.shot_ts is not None else None,
                "filesize": int(r.filesize or 0),
                "tags": tag_map.get(r.photo_id, []),
                "people": ppl_map.get(r.photo_id, []),
                "faces": faces_map.get(r.photo_id, []),
                "thumbnail": (
                    {
                        "mime_type": r.thumbnail_mime_type,
                        "width": int(r.thumbnail_width),
                        "height": int(r.thumbnail_height),
                        "data_base64": base64.b64encode(r.thumbnail_jpeg).decode("ascii"),
                    }
                    if r.thumbnail_jpeg and r.thumbnail_mime_type and r.thumbnail_width and r.thumbnail_height
                    else None
                ),
                "original": original_map.get(r.photo_id),
            }
            for r in rows
        ]

    def _load_original_availability(self, photo_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        rows = self.db.execute(
            select(
                self.photo_files.c.photo_id,
                self.watched_folders.c.availability_state.label("watched_folder_availability_state"),
                self.watched_folders.c.last_failure_reason.label("watched_folder_last_failure_reason"),
                self.storage_sources.c.availability_state.label("storage_source_availability_state"),
                self.storage_sources.c.last_failure_reason.label("storage_source_last_failure_reason"),
            )
            .select_from(
                self.photo_files.outerjoin(
                    self.watched_folders,
                    self.photo_files.c.watched_folder_id == self.watched_folders.c.watched_folder_id,
                ).outerjoin(
                    self.storage_sources,
                    self.watched_folders.c.storage_source_id == self.storage_sources.c.storage_source_id,
                )
            )
            .where(self.photo_files.c.photo_id.in_(photo_ids))
            .where(self.photo_files.c.deleted_ts.is_(None))
            .where(self.photo_files.c.lifecycle_state == "active")
            .order_by(self.photo_files.c.photo_id, self.photo_files.c.last_seen_ts.desc())
        ).mappings()

        availability: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            photo_id = row["photo_id"]
            if photo_id in availability:
                continue
            state = (
                row["watched_folder_availability_state"]
                or row["storage_source_availability_state"]
                or "unknown"
            )
            reason = (
                row["watched_folder_last_failure_reason"]
                or row["storage_source_last_failure_reason"]
            )
            availability[photo_id] = {
                "is_available": state == "active",
                "availability_state": state,
                "last_failure_reason": reason,
            }
        return availability

    def compute_facets(self, filtered_photo_ids: List[str], filters: SearchFilters | None = None) -> Dict[str, Any]:
        """Compute facets for the filtered photo set."""
        context = FacetContext(
            db=self.db,
            photo_tags=self.photo_tags,
            faces=self.faces,
            photos=self.photos,
            face_labels=self.face_labels,
            face_suggestions=self.face_suggestions,
            filters=filters,
        )
        
        tags_facet = TagsFacet()
        people_facet = PeopleFacet()
        has_faces_facet = HasFacesFacet()
        date_facet = DateHierarchyFacet()
        duplicates_facet = DuplicatesFacet()
        
        date_result = date_facet.compute(filtered_photo_ids, context)
        tags_result = tags_facet.compute(filtered_photo_ids, context)
        people_result = people_facet.compute(filtered_photo_ids, context)
        has_faces_result = has_faces_facet.compute(filtered_photo_ids, context)
        duplicates_result = duplicates_facet.compute(filtered_photo_ids, context)
        
        return {
            "date": self._format_date_facet(date_result),
            "people": self._format_simple_facet(people_result),
            "has_faces": self._format_boolean_facet(has_faces_result),
            "tags": self._format_simple_facet(tags_result),
            "duplicates": self._format_duplicates_facet(duplicates_result),
        }
    
    @staticmethod
    def _format_simple_facet(result: FacetResult) -> List[Dict[str, Any]]:
        """Convert a simple FacetResult into API response format."""
        return [
            {"value": value.value, "count": int(value.count)}
            for value in (result.values or [])
        ]
    
    @staticmethod
    def _format_date_facet(result: FacetResult) -> Dict[str, Any]:
        """Convert the hierarchical date FacetResult into nested dict format."""
        def serialize_year(year_val: FacetValue) -> Dict[str, Any]:
            return {
                "value": year_val.value,
                "count": int(year_val.count),
                "months": [serialize_month(m) for m in (year_val.children or [])],
            }
        
        def serialize_month(month_val: FacetValue) -> Dict[str, Any]:
            return {
                "value": month_val.value,
                "count": int(month_val.count),
                "days": [
                    {"value": day.value, "count": int(day.count)}
                    for day in (month_val.children or [])
                ],
            }
        
        years = [serialize_year(year_val) for year_val in (result.values or [])]
        return {"years": years}
    
    @staticmethod
    def _format_duplicates_facet(result: FacetResult) -> Dict[str, int]:
        """Convert duplicate facet metadata into API response format."""
        metadata = result.metadata or {}
        return {
            "exact": int(metadata.get("exact", 0) or 0),
            "near": int(metadata.get("near", 0) or 0),
        }

    @staticmethod
    def _format_boolean_facet(result: FacetResult) -> Dict[str, int]:
        return {
            str(value.value): int(value.count)
            for value in (result.values or [])
        }
