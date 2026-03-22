from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.storage import resolve_database_url


def upgrade_database(database_url: str | Path | None = None) -> None:
    config = Config(str(_alembic_ini_path()))
    config.set_main_option("script_location", str(_script_location()))
    config.set_main_option("sqlalchemy.url", resolve_database_url(database_url))
    command.upgrade(config, "head")


def _alembic_ini_path() -> Path:
    return Path(__file__).resolve().parents[1] / "alembic.ini"


def _script_location() -> Path:
    return Path(__file__).resolve().parents[1] / "alembic"
