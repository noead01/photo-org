from __future__ import annotations

import re


class PathNormalizationError(RuntimeError):
    pass


def normalize_operator_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if not normalized:
        return "/"

    prefix, remainder = _split_prefix(normalized)
    raw_parts = remainder.split("/")
    parts: list[str] = []
    for part in raw_parts:
        if not part or part == ".":
            continue
        if part == "..":
            raise PathNormalizationError(f"path {value!r} must not contain '..'")
        parts.append(part)
    if not parts:
        return prefix or "/"
    return prefix + "/".join(parts)


def _split_prefix(value: str) -> tuple[str, str]:
    match = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*://)(.*)$", value)
    if match is not None:
        return match.group(1), match.group(2)
    if value.startswith("//"):
        return "//", value[2:]
    if value.startswith("/"):
        return "/", value[1:]
    return "", value
