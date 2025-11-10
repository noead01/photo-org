# features/environment.py
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Iterator, Optional

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, Table, Column, MetaData, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# --- Import your app + DI hooks (ADAPT THESE) ---
from app.main import app
from app.dependencies import get_db
try:
    from app.dependencies import get_vector_search
    HAS_VECTOR = True
except Exception:
    HAS_VECTOR = False


def before_all(context):
    # SQLite in-memory DB
    context.engine = create_engine("sqlite+pysqlite:///:memory:", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    context.Session = sessionmaker(bind=context.engine, autoflush=False, autocommit=False, future=True)

    # Create minimal schema your API needs
    meta = MetaData()
    context.t_photos = Table("photos", meta,
        Column("photo_id", String, primary_key=True),
        Column("path", String, nullable=False),
        Column("sha256", String),
        Column("phash", String),
        Column("filesize", Integer),
        Column("ext", String),
        Column("camera_make", String),
        Column("orientation", String),
        Column("shot_ts", DateTime(timezone=True)),
    )
    context.t_faces = Table("faces", meta,
        Column("face_id", String, primary_key=True),
        Column("photo_id", String, ForeignKey("photos.photo_id"), nullable=False),
        Column("person_id", String),
    )
    context.t_photo_tags = Table("photo_tags", meta,
        Column("photo_id", String, ForeignKey("photos.photo_id"), primary_key=True),
        Column("tag", String, primary_key=True),
    )
    context.t_vectors = Table("vectors", meta,
        Column("photo_id", String, ForeignKey("photos.photo_id"), primary_key=True),
        Column("dim", Integer, nullable=False),
        Column("payload", String, nullable=False),  # JSON array of floats
    )
    meta.create_all(context.engine)

    # Seed dataset
    seed(context)

    # Override DI to use our in-memory session
    def _get_db() -> Iterator:
        db = context.Session()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _get_db

    # Optional: fake vector search
    if HAS_VECTOR:
        class FakeVectorSearch:
            # You can tailor this later to return predictable IDs
            def top_k(self, query_vector: List[float], k: int, scope_photo_ids: Optional[List[str]] = None) -> List[str]:
                # Return an empty list; your API should then intersect or handle gracefully.
                return []
        app.dependency_overrides[get_vector_search] = lambda: FakeVectorSearch()

    # HTTP client
    context.client = TestClient(app)

    # Shared test state
    context.search_url = "/api/v1/search"
    context.current_filters = {}
    context.last_response = None


def after_all(context):
    # nothing special; SQLite :memory: goes away automatically
    pass


def seed(context):
    S = context.Session()
    tz = timezone.utc

    def add_photo(i: int, **kw):
        pid = kw.get("photo_id") or str(uuid.uuid4())
        row = {
            "photo_id": pid,
            "path": kw.get("path", f"/lib/{i:04d}.jpg"),
            "sha256": kw.get("sha256"),
            "phash": kw.get("phash"),
            "filesize": kw.get("filesize", 1000 + i),
            "ext": kw.get("ext", "jpg"),
            "camera_make": kw.get("camera_make", "Canon" if i % 2 else "Apple"),
            "orientation": kw.get("orientation", "landscape" if i % 2 == 0 else "portrait"),
            "shot_ts": kw.get("shot_ts", datetime(2020, 6, 1, 12, tzinfo=tz) + timedelta(days=i)),
        }
        S.execute(context.t_photos.insert().values(**row))
        return row

    def add_face(photo_id: str, person_id: Optional[str]):
        S.execute(context.t_faces.insert().values(face_id=str(uuid.uuid4()), photo_id=photo_id, person_id=person_id))

    def add_tags(photo_id: str, tags: List[str]):
        for t in tags:
            S.execute(context.t_photo_tags.insert().values(photo_id=photo_id, tag=t))

    def add_vec(photo_id: str, v: List[float]):
        S.execute(context.t_vectors.insert().values(photo_id=photo_id, dim=len(v), payload=json.dumps(v)))

    # 120 photos, 2019..2021; diverse attributes
    for i in range(120):
        base_dt = datetime(2019, 12, 1, 10, tzinfo=tz) + timedelta(days=i * 8)
        row = add_photo(
            i,
            ext="heic" if i % 3 == 0 else ("jpg" if i % 3 == 1 else "png"),
            camera_make="Apple" if i % 4 in (0, 1) else "Canon",
            orientation="landscape" if i % 5 in (0, 1, 2) else "portrait",
            shot_ts=base_dt,
            path=f"/lib/{i:04d}_{'vacation' if i%6==0 else 'misc'}.{'heic' if i%3==0 else 'jpg'}",
            sha256=f"sha_{i//7}" if i % 7 in (0,1) else f"sha_{i}",
            phash=f"ph_{i//9}",
        )
        pid = row["photo_id"]

        tags = []
        if i % 6 == 0: tags.append("vacation")
        if i % 8 == 0: tags.append("beach")
        if i % 10 == 0: tags.append("sunset")
        if i % 9 == 0: tags.append("portrait")
        add_tags(pid, tags or ["misc"])

        if i % 2 == 0:
            add_face(pid, "person_ines")
            if i % 4 == 0:
                add_face(pid, "person_ines")  # second face same photo
        if i % 5 == 0:
            add_face(pid, "person_john")

        vec = [float((i % 40) / 39.0) for _ in range(128)]
        add_vec(pid, vec)

    S.commit()
    S.close()
