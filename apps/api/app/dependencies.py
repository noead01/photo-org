from typing import Iterator
import os
from sqlalchemy.orm import Session

from app.storage import create_session_factory


# In tests, Behave overrides get_db(). This default is only for dev/prod.
DATABASE_URL = os.getenv("DATABASE_URL")
_SessionLocal = create_session_factory(DATABASE_URL)

def get_db() -> Iterator[Session]:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
