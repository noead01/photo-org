from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db.config import resolve_database_url
from photoorg_db_schema import configure_embedding_column


def create_db_engine(database_url: str | Path | None = None) -> Engine:
    url = resolve_database_url(database_url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, future=True, connect_args=connect_args)
    configure_embedding_column(engine)
    return engine


def create_session_factory(database_url: str | Path | None = None) -> sessionmaker:
    engine = create_db_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
