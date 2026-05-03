from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


@dataclass(frozen=True)
class FaceDetection:
    face_id: str
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    bitmap: bytes | None
    embedding: list[float] | None
    provenance: dict[str, object]
    person_id: str | None = None

    def as_row(self) -> dict[str, object]:
        return asdict(self)


class OpenCvFaceDetector:
    def __init__(
        self,
        *,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_size: tuple[int, int] = (60, 60),
        max_size: tuple[int, int] | None = None,
        min_area_ratio: float = 0.0,
        max_area_ratio: float = 1.0,
        aspect_ratio_min: float = 0.0,
        aspect_ratio_max: float = 100.0,
    ) -> None:
        import cv2  # type: ignore

        _validate_detector_params(
            scale_factor=scale_factor,
            min_neighbors=min_neighbors,
            min_size=min_size,
            max_size=max_size,
            min_area_ratio=min_area_ratio,
            max_area_ratio=max_area_ratio,
            aspect_ratio_min=aspect_ratio_min,
            aspect_ratio_max=aspect_ratio_max,
        )

        self._cv2 = cv2
        self._scale_factor = scale_factor
        self._min_neighbors = min_neighbors
        self._min_size = min_size
        self._max_size = max_size
        self._min_area_ratio = min_area_ratio
        self._max_area_ratio = max_area_ratio
        self._aspect_ratio_min = aspect_ratio_min
        self._aspect_ratio_max = aspect_ratio_max

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        classifier = cv2.CascadeClassifier(cascade_path)
        if classifier.empty():
            raise RuntimeError(f"unable to load cascade classifier at {cascade_path}")
        self._classifier = classifier

    def detection_settings(self) -> dict[str, object]:
        return {
            "detector": "opencv-haarcascade",
            "model": "haarcascade_frontalface_default",
            "scale_factor": self._scale_factor,
            "min_neighbors": self._min_neighbors,
            "min_size": list(self._min_size),
            "max_size": list(self._max_size) if self._max_size is not None else None,
            "min_area_ratio": self._min_area_ratio,
            "max_area_ratio": self._max_area_ratio,
            "aspect_ratio_min": self._aspect_ratio_min,
            "aspect_ratio_max": self._aspect_ratio_max,
        }

    def detect(self, path: Path) -> list[dict]:
        import numpy as np  # type: ignore
        from PIL import Image, ImageOps  # type: ignore
        from pillow_heif import register_heif_opener  # type: ignore

        register_heif_opener()

        with Image.open(path) as image:
            prepared = ImageOps.exif_transpose(image)
            rgb_image = prepared.convert("RGB")
            width, height = rgb_image.size
            grayscale = self._cv2.cvtColor(np.array(rgb_image), self._cv2.COLOR_RGB2GRAY)
            detection_params: dict[str, object] = {
                "scaleFactor": self._scale_factor,
                "minNeighbors": self._min_neighbors,
                "minSize": self._min_size,
            }
            if self._max_size is not None:
                detection_params["maxSize"] = self._max_size
            boxes = self._classifier.detectMultiScale(
                grayscale,
                **detection_params,
            )

            detections: list[dict] = []
            for index, (x, y, w, h) in enumerate(boxes):
                if not self._passes_bbox_filters(
                    bbox_w=int(w),
                    bbox_h=int(h),
                    image_width=width,
                    image_height=height,
                ):
                    continue
                crop = rgb_image.crop((max(0, x), max(0, y), min(width, x + w), min(height, y + h)))
                face_id = str(uuid5(NAMESPACE_URL, f"{path.resolve()}:{x}:{y}:{w}:{h}:{index}"))
                detections.append(
                    FaceDetection(
                        face_id=face_id,
                        bbox_x=int(x),
                        bbox_y=int(y),
                        bbox_w=int(w),
                        bbox_h=int(h),
                        bitmap=_encode_jpeg(crop),
                        embedding=None,
                        provenance={
                            **self.detection_settings(),
                            "bbox_space_width": width,
                            "bbox_space_height": height,
                        },
                    ).as_row()
                )

        return detections

    def _passes_bbox_filters(
        self,
        *,
        bbox_w: int,
        bbox_h: int,
        image_width: int,
        image_height: int,
    ) -> bool:
        if bbox_w <= 0 or bbox_h <= 0 or image_width <= 0 or image_height <= 0:
            return False
        area_ratio = (bbox_w * bbox_h) / float(image_width * image_height)
        if area_ratio < self._min_area_ratio:
            return False
        if area_ratio > self._max_area_ratio:
            return False
        aspect_ratio = bbox_w / float(bbox_h)
        if aspect_ratio < self._aspect_ratio_min:
            return False
        if aspect_ratio > self._aspect_ratio_max:
            return False
        return True


def create_default_face_detector() -> OpenCvFaceDetector:
    scale_factor = _read_float("FACE_DETECT_SCALE_FACTOR", default=1.1)
    min_neighbors = _read_int("FACE_DETECT_MIN_NEIGHBORS", default=5)
    min_size = _read_size("FACE_DETECT_MIN_SIZE", default=(60, 60))
    max_size = _read_optional_size("FACE_DETECT_MAX_SIZE")
    min_area_ratio = _read_float("FACE_DETECT_MIN_AREA_RATIO", default=0.0)
    max_area_ratio = _read_float("FACE_DETECT_MAX_AREA_RATIO", default=1.0)
    aspect_ratio_min = _read_float("FACE_DETECT_ASPECT_RATIO_MIN", default=0.0)
    aspect_ratio_max = _read_float("FACE_DETECT_ASPECT_RATIO_MAX", default=100.0)

    return OpenCvFaceDetector(
        scale_factor=scale_factor,
        min_neighbors=min_neighbors,
        min_size=min_size,
        max_size=max_size,
        min_area_ratio=min_area_ratio,
        max_area_ratio=max_area_ratio,
        aspect_ratio_min=aspect_ratio_min,
        aspect_ratio_max=aspect_ratio_max,
    )


def _read_float(name: str, *, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be a float, got {raw_value!r}") from exc


def _read_int(name: str, *, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw_value!r}") from exc


def _read_size(name: str, *, default: tuple[int, int]) -> tuple[int, int]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return _parse_size(raw_value, env_name=name)


def _read_optional_size(name: str) -> tuple[int, int] | None:
    raw_value = os.getenv(name)
    if raw_value is None:
        return None
    text = raw_value.strip()
    if text == "":
        return None
    return _parse_size(text, env_name=name)


def _parse_size(raw_value: str, *, env_name: str) -> tuple[int, int]:
    normalized = raw_value.strip().lower().replace(" ", "")
    parts = normalized.split("x")
    if len(parts) != 2:
        raise ValueError(f"{env_name} must use WIDTHxHEIGHT format, got {raw_value!r}")
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError as exc:
        raise ValueError(f"{env_name} must use WIDTHxHEIGHT format, got {raw_value!r}") from exc
    return (width, height)


def _validate_detector_params(
    *,
    scale_factor: float,
    min_neighbors: int,
    min_size: tuple[int, int],
    max_size: tuple[int, int] | None,
    min_area_ratio: float,
    max_area_ratio: float,
    aspect_ratio_min: float,
    aspect_ratio_max: float,
) -> None:
    if scale_factor <= 1.0:
        raise ValueError("scale_factor must be greater than 1.0")
    if min_neighbors < 0:
        raise ValueError("min_neighbors must be non-negative")
    if min_size[0] <= 0 or min_size[1] <= 0:
        raise ValueError("min_size values must be positive")
    if max_size is not None and (max_size[0] <= 0 or max_size[1] <= 0):
        raise ValueError("max_size values must be positive")
    if max_size is not None and (max_size[0] < min_size[0] or max_size[1] < min_size[1]):
        raise ValueError("max_size must be greater than or equal to min_size")
    if min_area_ratio < 0.0:
        raise ValueError("min_area_ratio must be non-negative")
    if max_area_ratio <= 0.0:
        raise ValueError("max_area_ratio must be greater than zero")
    if min_area_ratio > max_area_ratio:
        raise ValueError("min_area_ratio must be less than or equal to max_area_ratio")
    if aspect_ratio_min < 0.0:
        raise ValueError("aspect_ratio_min must be non-negative")
    if aspect_ratio_max <= 0.0:
        raise ValueError("aspect_ratio_max must be greater than zero")
    if aspect_ratio_min > aspect_ratio_max:
        raise ValueError("aspect_ratio_min must be less than or equal to aspect_ratio_max")


def _encode_jpeg(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()
