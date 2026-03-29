from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


SUPPORTED_EXTENSIONS = {".heic", ".heif", ".jpeg", ".jpg", ".png"}


@dataclass
class IngestResult:
    scanned: int = 0
    enqueued: int = 0
    inserted: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)


def iter_photo_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path
