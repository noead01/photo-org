from typing import Iterator
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# In tests, Behave overrides get_db(). This default is only for dev/prod.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./photoorg.db")

_engine = create_engine(DATABASE_URL, future=True)
_SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)

def get_db() -> Iterator[Session]:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
