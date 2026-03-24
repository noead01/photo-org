from __future__ import annotations

import os
import sys

import uvicorn

from app import migrations


def run_entrypoint(database_url: str | None = None) -> None:
    try:
        migrations.upgrade_database(database_url)
    except Exception as exc:
        print(f"migration_failed={exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


def main() -> int:
    run_entrypoint(os.getenv("DATABASE_URL"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
