from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import sessionmaker

from photoorg_db_schema import (
    configure_embedding_column,
    face_labels,
    faces,
    ingest_runs,
    metadata,
    people,
    photo_files,
    photo_tags,
    photos,
    watched_folders,
)

DEFAULT_SQLITE_PATH = Path("apps/api/photoorg.db").resolve()
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"


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
    configure_embedding_column(engine)
    return engine


def create_session_factory(database_url: str | Path | None = None) -> sessionmaker:
    engine = create_db_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_schema(bind: Engine | Connection) -> None:
    connection = bind.connect() if isinstance(bind, Engine) else bind
    close_after = isinstance(bind, Engine)
    try:
        if connection.dialect.name == "postgresql":
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            configure_embedding_column(connection)
        metadata.create_all(connection)
    finally:
        if close_after:
            connection.commit()
            connection.close()
