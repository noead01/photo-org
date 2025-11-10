from sqlalchemy import and_, or_, select, text
from sqlalchemy.sql import Select
from sqlalchemy import Table
from typing import List, Any, Tuple, Optional
from datetime import datetime
from app.core.enums import FilesizeRange

def build_base_query(photos: Table) -> Select:
    return select(
        photos.c.photo_id, photos.c.path, photos.c.ext, photos.c.camera_make,
        photos.c.orientation, photos.c.shot_ts, photos.c.filesize,
        photos.c.sha256, photos.c.phash
    )

def build_filters(sel: Select,
                  photos: Table, faces: Table, photo_tags: Table,
                  filters: dict, q: Optional[str]) -> Tuple[Select, List[Any]]:
    where = []
    # date
    d = filters.get("date") or {}
    if d.get("from"):
        where.append(photos.c.shot_ts >= text(f"'{d['from']}T00:00:00Z'"))
    if d.get("to"):
        where.append(photos.c.shot_ts <= text(f"'{d['to']}T23:59:59Z'"))
    # plain lists
    for key, col in (("camera_make", photos.c.camera_make),
                     ("extension", photos.c.ext),
                     ("orientation", photos.c.orientation)):
        vals = filters.get(key)
        if vals:
            where.append(col.in_(vals))
    # filesize_range
    if filters.get("filesize_range"):
        lo, hi = filters["filesize_range"].bounds()
        where.append(and_(photos.c.filesize >= lo, photos.c.filesize < hi))
    # has_faces
    if filters.get("has_faces") is True:
        sub = select(faces.c.photo_id).where(faces.c.photo_id == photos.c.photo_id).limit(1)
        where.append(sub.exists())
    # people OR
    if filters.get("people"):
        ppl = list(filters["people"])
        sub = select(faces.c.photo_id).where(and_(faces.c.photo_id == photos.c.photo_id,
                                                  faces.c.person_id.in_(ppl))).limit(1)
        where.append(sub.exists())
    # tags OR
    if filters.get("tags"):
        tags = list(filters["tags"])
        sub = select(photo_tags.c.photo_id).where(and_(photo_tags.c.photo_id == photos.c.photo_id,
                                                       photo_tags.c.tag.in_(tags))).limit(1)
        where.append(sub.exists())
    # lightweight q
    if q:
        toks = [t for t in q.lower().split() if t]
        if toks:
            tag_exists = select(photo_tags.c.photo_id).where(
                (photo_tags.c.photo_id == photos.c.photo_id) &
                or_(*[photo_tags.c.tag.ilike(f"%{t}%") for t in toks])
            ).limit(1).exists()
            where.append(or_(photos.c.path.ilike(f"%{toks[0]}%"), tag_exists))

    if where:
        sel = sel.where(and_(*where))
    return sel, where
