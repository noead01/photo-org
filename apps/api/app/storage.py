from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Column,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Float,
    String,
    Table,
    Text,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


DEFAULT_SQLITE_PATH = Path("apps/api/photoorg.db").resolve()
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"
EMBEDDING_DIMENSION = 128


try:
    from pgvector.sqlalchemy import Vector
except ModuleNotFoundError:  # pragma: no cover - exercised when pgvector is absent
    Vector = None


metadata = MetaData()


def embedding_column_type(dialect_name: str | None = None) -> Any:
    if dialect_name == "postgresql":
        if Vector is None:
            raise RuntimeError(
                "pgvector is required for PostgreSQL embeddings. Install the 'pgvector' package."
            )
        return Vector(EMBEDDING_DIMENSION)
    return JSON()


photos = Table(
    "photos",
    metadata,
    Column("photo_id", String, primary_key=True),
    Column("path", Text, nullable=False, unique=True),
    Column("sha256", String, nullable=False),
    Column("phash", String),
    Column("filesize", Integer, nullable=False),
    Column("ext", String, nullable=False),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False),
    Column("modified_ts", TIMESTAMP(timezone=True), nullable=False),
    Column("shot_ts", TIMESTAMP(timezone=True)),
    Column("shot_ts_source", String),
    Column("camera_make", String),
    Column("camera_model", String),
    Column("software", String),
    Column("orientation", String),
    Column("gps_latitude", Float),
    Column("gps_longitude", Float),
    Column("gps_altitude", Float),
    Column("faces_count", Integer, nullable=False, server_default=text("0")),
    Column("faces_detected_ts", TIMESTAMP(timezone=True)),
)

faces = Table(
    "faces",
    metadata,
    Column("face_id", String, primary_key=True),
    Column("photo_id", String, ForeignKey("photos.photo_id", ondelete="CASCADE"), nullable=False),
    Column("person_id", String),
    Column("bbox_x", Integer),
    Column("bbox_y", Integer),
    Column("bbox_w", Integer),
    Column("bbox_h", Integer),
    Column("bitmap", LargeBinary),
    Column("embedding", JSON()),
    Column("provenance", JSON()),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

photo_tags = Table(
    "photo_tags",
    metadata,
    Column("photo_id", String, ForeignKey("photos.photo_id", ondelete="CASCADE"), primary_key=True),
    Column("tag", String, primary_key=True),
)

people = Table(
    "people",
    metadata,
    Column("person_id", String, primary_key=True),
    Column("display_name", String, nullable=False),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

face_labels = Table(
    "face_labels",
    metadata,
    Column("face_id", String, ForeignKey("faces.face_id", ondelete="CASCADE"), primary_key=True),
    Column("person_id", String, ForeignKey("people.person_id", ondelete="CASCADE"), primary_key=True),
    Column("label_source", String, nullable=False),
    Column("confidence", Float),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_photos_shot_ts", photos.c.shot_ts)
Index("idx_photos_sha256", photos.c.sha256)
Index("idx_faces_photo_id", faces.c.photo_id)
Index("idx_photo_tags_photo_id", photo_tags.c.photo_id)


def resolve_database_url(database_url: str | Path | None = None) -> str:
    if database_url is None:
        return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if isinstance(database_url, Path):
        return f"sqlite:///{database_url.expanduser().resolve()}"

    text_value = str(database_url)
    if "://" in text_value:
        return text_value
    return f"sqlite:///{Path(text_value).expanduser().resolve()}"


def create_db_engine(database_url: str | Path | None = None) -> Engine:
    url = resolve_database_url(database_url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, future=True, connect_args=connect_args)
    _configure_embedding_column(engine)
    return engine


def create_session_factory(database_url: str | Path | None = None) -> sessionmaker:
    engine = create_db_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def _configure_embedding_column(bind: Engine) -> None:
    dialect_name = bind.dialect.name
    faces.c.embedding.type = embedding_column_type(dialect_name)
