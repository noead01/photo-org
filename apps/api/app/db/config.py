from __future__ import annotations

import os
from pathlib import Path


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
