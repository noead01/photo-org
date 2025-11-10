from typing import List, Dict, Any
from sqlalchemy import MetaData, Table, select, func, or_, and_
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

class PhotosRepository:
    def __init__(self, db: Session):
        self.db = db
        bind = db.get_bind()
        md = MetaData()
        # Explicit autoload per table (no global reflect, no helpers needed)
        self.photos: Table     = Table("photos", md, autoload_with=bind)
        self.faces: Table      = Table("faces", md, autoload_with=bind)
        self.photo_tags: Table = Table("photo_tags", md, autoload_with=bind)

    def select_hits(self, sel, order_desc, limit: int, cursor: str | None) -> List[Row]:
        from app.core.pagination import decode_cursor
        sel = sel.order_by(*order_desc)
        if cursor:
            last_ts, last_pid = decode_cursor(cursor)
            sel = sel.where(or_(self.photos.c.shot_ts < last_ts,
                                and_(self.photos.c.shot_ts == last_ts,
                                     self.photos.c.photo_id < last_pid)))
        return list(self.db.execute(sel.limit(limit)).all())

    def count_total(self, sel) -> int:
        return int(self.db.execute(select(func.count()).select_from(sel.subquery())).scalar_one())

    def hydrate_items(self, rows: List[Row]) -> List[Dict[str, Any]]:
        if not rows:
            return []
        pids = [r.photo_id for r in rows]

        tag_map  = {pid: [] for pid in pids}
        ppl_map  = {pid: [] for pid in pids}
        faces_map = {pid: [] for pid in pids}

        for r in self.db.execute(
            select(self.photo_tags.c.photo_id, self.photo_tags.c.tag)
            .where(self.photo_tags.c.photo_id.in_(pids))
        ).all():
            tag_map[r.photo_id].append(r.tag)

        for r in self.db.execute(
            select(self.faces.c.photo_id, self.faces.c.person_id)
            .where(self.faces.c.photo_id.in_(pids))
        ).all():
            if r.person_id:
                ppl_map[r.photo_id].append(r.person_id)
            faces_map[r.photo_id].append({"person_id": r.person_id})

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
