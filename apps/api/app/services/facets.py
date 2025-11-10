from typing import Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.orm import Session

def date_facet(db: Session, photos, filt_ids: List[str]) -> Dict[str, Any]:
    rows = db.execute(select(photos.c.shot_ts).where(photos.c.photo_id.in_(filt_ids))).all()
    by_year: Dict[int, Dict[str, Any]] = {}
    from datetime import datetime
    for (ts,) in rows:
        if not isinstance(ts, datetime): continue
        y, m, d = ts.year, ts.month, ts.day
        yb = by_year.setdefault(y, {"value": y, "count": 0, "months": {}})
        yb["count"] += 1
        mb = yb["months"].setdefault(m, {"value": m, "count": 0, "days": {}})
        mb["count"] += 1
        mb["days"][d] = mb["days"].get(d, 0) + 1
    years = []
    for y in sorted(by_year):
        months = []
        for m in sorted(by_year[y]["months"]):
            days = [{"value": dd, "count": by_year[y]["months"][m]["days"][dd]} for dd in sorted(by_year[y]["months"][m]["days"])]
            months.append({"value": m, "count": by_year[y]["months"][m]["count"], "days": days})
        years.append({"value": y, "count": by_year[y]["count"], "months": months})
    return {"years": years}

def people_facet(db: Session, faces, filt_ids: List[str]) -> List[Dict[str, Any]]:
    rows = db.execute(
        select(faces.c.person_id, func.count(func.distinct(faces.c.photo_id)))
        .where(faces.c.photo_id.in_(filt_ids)).group_by(faces.c.person_id)
    ).all()
    return [{"value": pid, "count": int(cnt)} for (pid, cnt) in rows if pid]

def tags_facet(db: Session, photo_tags, filt_ids: List[str]) -> List[Dict[str, Any]]:
    rows = db.execute(
        select(photo_tags.c.tag, func.count(func.distinct(photo_tags.c.photo_id)))
        .where(photo_tags.c.photo_id.in_(filt_ids)).group_by(photo_tags.c.tag)
    ).all()
    return [{"value": t, "count": int(c)} for (t, c) in rows]

def duplicates_facet(db: Session, photos, filt_ids: List[str]) -> Dict[str, int]:
    e = db.execute(
        select(func.count()).select_from(
            select(photos.c.sha256, func.count().label("c"))
            .where(photos.c.photo_id.in_(filt_ids)).group_by(photos.c.sha256).having(func.count() > 1).subquery()
        )
    ).scalar_one()
    n = db.execute(
        select(func.count()).select_from(
            select(photos.c.phash, func.count().label("c"))
            .where(photos.c.photo_id.in_(filt_ids)).group_by(photos.c.phash).having(func.count() > 1).subquery()
        )
    ).scalar_one()
    return {"exact": int(e or 0), "near": int(n or 0)}
