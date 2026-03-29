from __future__ import annotations

import posixpath
from pathlib import Path


def normalize_absolute_path_root(path: str | Path) -> str:
    raw = str(path).replace("\\", "/")
    normalized = posixpath.normpath(raw)
    if not normalized.startswith("/"):
        raise ValueError("path root must be absolute")
    return normalized


def relative_photo_path(root: Path, path: Path) -> str:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    return normalize_relative_path(relative)


def normalize_relative_path(path: str) -> str:
    normalized = posixpath.normpath(path.replace("\\", "/"))
    if normalized in {".", ""}:
        raise ValueError("relative path must not be empty")
    if normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
        raise ValueError("relative path must stay within the watched folder")
    return normalized


def build_rooted_photo_path(path_root: str | Path, relative_path: str) -> str:
    mount_root = normalize_absolute_path_root(path_root)
    normalized_relative = normalize_relative_path(relative_path)
    return posixpath.normpath(posixpath.join(mount_root, normalized_relative))


def build_source_aware_photo_path(storage_source_id: str, relative_path: str) -> str:
    normalized_relative = normalize_relative_path(relative_path)
    return posixpath.normpath(
        posixpath.join("/storage-sources", storage_source_id, normalized_relative)
    )
