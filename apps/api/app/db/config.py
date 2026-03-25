from __future__ import annotations

import os
from pathlib import Path


DEFAULT_SQLITE_PATH = Path("apps/api/photoorg.db").resolve()
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"
DEFAULT_MISSING_FILE_GRACE_PERIOD_DAYS = 1


def resolve_database_url(database_url: str | Path | None = None) -> str:
    if database_url is None:
        return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if isinstance(database_url, Path):
        return f"sqlite:///{database_url.expanduser().resolve()}"

    text_value = str(database_url)
    if "://" in text_value:
        return text_value
    return f"sqlite:///{Path(text_value).expanduser().resolve()}"


def resolve_missing_file_grace_period_days(value: int | None = None) -> int:
    if value is None:
        value = int(
            os.getenv(
                "MISSING_FILE_GRACE_PERIOD_DAYS",
                str(DEFAULT_MISSING_FILE_GRACE_PERIOD_DAYS),
            )
        )
    if value < 0:
        raise ValueError("missing file grace period days must be non-negative")
    return value
