from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


_SHOT_DATETIME_ALIASES: tuple[tuple[str, str], ...] = (
    ("exif_ifd", "DateTimeOriginal"),
    ("exif_ifd", "DateTimeDigitized"),
    ("exif", "DateTimeOriginal"),
    ("exif", "DateTimeDigitized"),
    ("exif", "DateTime"),
)
_SHOT_SUBSEC_ALIASES: tuple[tuple[str, str], ...] = (
    ("exif_ifd", "SubsecTimeOriginal"),
    ("exif_ifd", "SubsecTimeDigitized"),
    ("exif_ifd", "SubsecTime"),
    ("exif", "SubsecTimeOriginal"),
    ("exif", "SubsecTimeDigitized"),
    ("exif", "SubsecTime"),
)
_SHOT_OFFSET_ALIASES: tuple[tuple[str, str], ...] = (
    ("exif_ifd", "OffsetTimeOriginal"),
    ("exif_ifd", "OffsetTimeDigitized"),
    ("exif_ifd", "OffsetTime"),
    ("exif", "OffsetTimeOriginal"),
    ("exif", "OffsetTimeDigitized"),
    ("exif", "OffsetTime"),
)
_MAPPED_EXIF_ATTRIBUTES: frozenset[tuple[str, str]] = frozenset(
    {
        *_SHOT_DATETIME_ALIASES,
        *_SHOT_SUBSEC_ALIASES,
        *_SHOT_OFFSET_ALIASES,
        ("exif", "Orientation"),
        ("exif", "Make"),
        ("exif", "Model"),
        ("exif", "Software"),
        ("gps_ifd", "GPSLatitude"),
        ("gps_ifd", "GPSLatitudeRef"),
        ("gps_ifd", "GPSLongitude"),
        ("gps_ifd", "GPSLongitudeRef"),
        ("gps_ifd", "GPSAltitude"),
        ("gps_ifd", "GPSAltitudeRef"),
    }
)


@dataclass(frozen=True)
class ImageMetadata:
    shot_ts: str | None = None
    shot_ts_source: str | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    software: str | None = None
    orientation: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    gps_altitude: float | None = None
    exif_attributes: dict[str, Any] | None = None
    exif_unmapped_attributes: dict[str, Any] | None = None


def extract_image_metadata(path: Path) -> ImageMetadata:
    try:
        from PIL import Image, ExifTags  # type: ignore
        from pillow_heif import register_heif_opener  # type: ignore
    except ModuleNotFoundError:
        return ImageMetadata()

    try:
        register_heif_opener()
        with Image.open(path) as image:
            exif = image.getexif()
            if not exif:
                return ImageMetadata()
    except Exception:
        return ImageMetadata()

    tag_names = {tag_id: name for tag_id, name in ExifTags.TAGS.items()}
    gps_tag_names = {tag_id: name for tag_id, name in ExifTags.GPSTAGS.items()}
    exif_map: dict[str, Any] = {
        tag_names.get(tag_id, str(tag_id)): value for tag_id, value in exif.items()
    }
    exif_ifd = _read_ifd(exif, 0x8769, tag_names)
    gps_ifd = _read_ifd(exif, 0x8825, gps_tag_names)
    exif_attributes, exif_unmapped_attributes = _collect_exif_attributes(exif_map, exif_ifd, gps_ifd)

    shot_ts = _extract_shot_timestamp(exif_map, exif_ifd)
    orientation = exif_map.get("Orientation")
    if orientation is not None:
        orientation = str(orientation)

    camera_make = exif_map.get("Make")
    if camera_make is not None:
        camera_make = str(camera_make).strip() or None

    camera_model = exif_map.get("Model")
    if camera_model is not None:
        camera_model = str(camera_model).strip() or None

    software = exif_map.get("Software")
    if software is not None:
        software = str(software).strip() or None

    latitude = _gps_coordinate(
        gps_ifd.get("GPSLatitude"),
        gps_ifd.get("GPSLatitudeRef"),
    )
    longitude = _gps_coordinate(
        gps_ifd.get("GPSLongitude"),
        gps_ifd.get("GPSLongitudeRef"),
    )
    altitude = _gps_altitude(
        gps_ifd.get("GPSAltitude"),
        gps_ifd.get("GPSAltitudeRef"),
    )

    return ImageMetadata(
        shot_ts=shot_ts,
        shot_ts_source=_shot_ts_source(shot_ts, exif_map, exif_ifd),
        camera_make=camera_make,
        camera_model=camera_model,
        software=software,
        orientation=orientation,
        gps_latitude=latitude,
        gps_longitude=longitude,
        gps_altitude=altitude,
        exif_attributes=exif_attributes or None,
        exif_unmapped_attributes=exif_unmapped_attributes or None,
    )


def stat_timestamp_to_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).replace(microsecond=0).isoformat()


def _normalize_exif_datetime(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=UTC).isoformat()
        except ValueError:
            continue

    return None


def _extract_shot_timestamp(exif_map: dict[str, Any], exif_ifd: dict[str, Any]) -> str | None:
    raw_value, _ = _first_semantic_value(
        exif_map,
        exif_ifd,
        _SHOT_DATETIME_ALIASES,
    )
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text:
        return None

    parsed = _parse_exif_datetime(text)
    if parsed is None:
        return None

    subsec, _ = _first_semantic_value(exif_map, exif_ifd, _SHOT_SUBSEC_ALIASES)
    if subsec is not None:
        digits = "".join(ch for ch in str(subsec) if ch.isdigit())[:6]
        if digits:
            parsed = parsed.replace(microsecond=int(digits.ljust(6, "0")))

    offset, _ = _first_semantic_value(exif_map, exif_ifd, _SHOT_OFFSET_ALIASES)
    offset_text = str(offset).strip() if offset is not None else ""
    if offset_text and _valid_offset(offset_text):
        return parsed.isoformat() + offset_text

    return parsed.replace(tzinfo=UTC).isoformat()


def _shot_ts_source(shot_ts: str | None, exif_map: dict[str, Any], exif_ifd: dict[str, Any]) -> str | None:
    if shot_ts is None:
        return None

    _value, source = _first_semantic_value(
        exif_map,
        exif_ifd,
        _SHOT_DATETIME_ALIASES,
    )
    if source is None:
        return "exif"
    return source


def _first_semantic_value(
    exif_map: dict[str, Any],
    exif_ifd: dict[str, Any],
    aliases: tuple[tuple[str, str], ...],
) -> tuple[Any | None, str | None]:
    sources = {
        "exif": exif_map,
        "exif_ifd": exif_ifd,
    }
    for namespace, tag_name in aliases:
        container = sources[namespace]
        value = container.get(tag_name)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        return value, f"{namespace}:{tag_name}"
    return None, None


def _read_ifd(exif: Any, ifd_id: int, tag_names: dict[int, str]) -> dict[str, Any]:
    if not hasattr(exif, "get_ifd"):
        return {}
    try:
        raw_ifd = exif.get_ifd(ifd_id) or {}
    except Exception:
        return {}
    return {tag_names.get(tag_id, str(tag_id)): value for tag_id, value in raw_ifd.items()}


def _gps_coordinate(value: Any, reference: Any) -> float | None:
    if value is None or reference is None:
        return None
    try:
        degrees, minutes, seconds = value
        decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    except Exception:
        return None
    ref = str(reference).upper()
    if ref in {"S", "W"}:
        decimal *= -1
    return round(decimal, 7)


def _gps_altitude(value: Any, reference: Any) -> float | None:
    if value is None:
        return None
    try:
        altitude = float(value)
    except Exception:
        return None

    if reference in {1, b"\x01", "1"}:
        altitude *= -1
    return round(altitude, 3)


def _valid_offset(value: str) -> bool:
    if len(value) != 6:
        return False
    if value[0] not in {"+", "-"}:
        return False
    return value[1:3].isdigit() and value[3] == ":" and value[4:6].isdigit()


def _parse_exif_datetime(value: str) -> datetime | None:
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _collect_exif_attributes(
    exif_map: dict[str, Any],
    exif_ifd: dict[str, Any],
    gps_ifd: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    qualified: dict[str, Any] = {}
    for namespace, values in (
        ("exif", exif_map),
        ("exif_ifd", exif_ifd),
        ("gps_ifd", gps_ifd),
    ):
        for tag_name, raw_value in values.items():
            qualified_name = f"{namespace}.{tag_name}"
            qualified[qualified_name] = _serialize_exif_value(raw_value)

    unmapped: dict[str, Any] = {}
    for qualified_name, value in qualified.items():
        namespace, tag_name = qualified_name.split(".", 1)
        if (namespace, tag_name) in _MAPPED_EXIF_ATTRIBUTES:
            continue
        unmapped[qualified_name] = value

    return qualified, unmapped


def _serialize_exif_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, list | tuple):
        return [_serialize_exif_value(component) for component in value]
    if isinstance(value, dict):
        return {str(key): _serialize_exif_value(component) for key, component in value.items()}
    return str(value)
