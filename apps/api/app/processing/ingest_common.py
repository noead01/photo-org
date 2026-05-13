from __future__ import annotations

import os
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
    for current_root, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        root_path = Path(current_root)
        for filename in filenames:
            path = root_path / filename
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                yield path
