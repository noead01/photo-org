from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

FACE_DETECT_PROFILE_ENV = "FACE_DETECT_PROFILE"
FACE_DETECT_PROFILE_FILE_ENV = "FACE_DETECT_PROFILE_FILE"
FACE_RECOGNITION_SFACE_MODEL_FILE_ENV = "FACE_RECOGNITION_SFACE_MODEL_FILE"
DEFAULT_FACE_DETECT_PROFILE = "balanced"
DEFAULT_FACE_DETECT_PROFILE_FILE = Path(__file__).with_name("face_detect_profiles.json")

_FACE_DETECT_PROFILE_ALIASES = {
    "default": "balanced",
    "standard": "balanced",
    "strict": "high_precision",
    "precision": "high_precision",
    "high-precision": "high_precision",
    "high-recall": "high_recall",
    "recall": "high_recall",
    "portrait": "portraits",
}


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


class FaceEmbeddingExtractor(Protocol):
    def extract(self, image: object) -> list[float] | None:
        pass

    def provenance(self) -> dict[str, object]:
        pass


class OpenCvSFaceEmbeddingExtractor:
    def __init__(
        self,
        model_file: str | Path,
        *,
        input_size: tuple[int, int] = (112, 112),
    ) -> None:
        import cv2  # type: ignore

        self._cv2 = cv2
        self._model_file = Path(model_file).expanduser()
        self._input_size = input_size
        if not self._model_file.is_file():
            raise FileNotFoundError(f"SFace model file not found: {self._model_file}")
        self._recognizer = cv2.FaceRecognizerSF_create(str(self._model_file), "")

    def provenance(self) -> dict[str, object]:
        return {
            "extractor": "opencv-sface",
            "model": str(self._model_file),
            "input_size": list(self._input_size),
        }

    def extract(self, image: object) -> list[float] | None:
        import numpy as np  # type: ignore

        if hasattr(image, "convert"):
            image = image.convert("RGB")
        rgb = np.array(image)
        bgr = self._cv2.cvtColor(rgb, self._cv2.COLOR_RGB2BGR)
        resized = self._cv2.resize(bgr, self._input_size)
        feature = self._recognizer.feature(resized)
        return _normalize_feature_vector(feature)


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
        embedding_extractor: FaceEmbeddingExtractor | None = None,
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
        self._embedding_extractor = embedding_extractor

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
                embedding = None
                provenance = {
                    **self.detection_settings(),
                    "bbox_space_width": width,
                    "bbox_space_height": height,
                }
                if self._embedding_extractor is not None:
                    embedding = self._embedding_extractor.extract(crop)
                    if embedding is not None:
                        provenance["embedding"] = self._embedding_extractor.provenance()
                face_id = str(uuid5(NAMESPACE_URL, f"{path.resolve()}:{x}:{y}:{w}:{h}:{index}"))
                detections.append(
                    FaceDetection(
                        face_id=face_id,
                        bbox_x=int(x),
                        bbox_y=int(y),
                        bbox_w=int(w),
                        bbox_h=int(h),
                        bitmap=_encode_jpeg(crop),
                        embedding=embedding,
                        provenance=provenance,
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
    _profile_name, profile_defaults = _resolve_face_detect_profile()
    scale_factor = _read_float("FACE_DETECT_SCALE_FACTOR", default=float(profile_defaults["scale_factor"]))
    min_neighbors = _read_int("FACE_DETECT_MIN_NEIGHBORS", default=int(profile_defaults["min_neighbors"]))
    min_size = _read_size("FACE_DETECT_MIN_SIZE", default=tuple(profile_defaults["min_size"]))
    max_size = _read_optional_size("FACE_DETECT_MAX_SIZE", default=profile_defaults["max_size"])
    min_area_ratio = _read_float(
        "FACE_DETECT_MIN_AREA_RATIO", default=float(profile_defaults["min_area_ratio"])
    )
    max_area_ratio = _read_float(
        "FACE_DETECT_MAX_AREA_RATIO", default=float(profile_defaults["max_area_ratio"])
    )
    aspect_ratio_min = _read_float(
        "FACE_DETECT_ASPECT_RATIO_MIN", default=float(profile_defaults["aspect_ratio_min"])
    )
    aspect_ratio_max = _read_float(
        "FACE_DETECT_ASPECT_RATIO_MAX", default=float(profile_defaults["aspect_ratio_max"])
    )
    embedding_extractor = _create_default_embedding_extractor()

    return OpenCvFaceDetector(
        scale_factor=scale_factor,
        min_neighbors=min_neighbors,
        min_size=min_size,
        max_size=max_size,
        min_area_ratio=min_area_ratio,
        max_area_ratio=max_area_ratio,
        aspect_ratio_min=aspect_ratio_min,
        aspect_ratio_max=aspect_ratio_max,
        embedding_extractor=embedding_extractor,
    )


def _create_default_embedding_extractor() -> FaceEmbeddingExtractor | None:
    model_file = os.getenv(FACE_RECOGNITION_SFACE_MODEL_FILE_ENV)
    if model_file is None or model_file.strip() == "":
        return None
    return OpenCvSFaceEmbeddingExtractor(model_file.strip())


def _normalize_feature_vector(value: object) -> list[float] | None:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list | tuple) and len(value) == 1 and isinstance(value[0], list | tuple):
        value = value[0]
    if not isinstance(value, list | tuple):
        return None
    try:
        feature = [float(component) for component in value]
    except (TypeError, ValueError):
        return None
    magnitude = math.sqrt(sum(component * component for component in feature))
    if magnitude <= 0.0:
        return None
    return [component / magnitude for component in feature]


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


def _read_optional_size(name: str, *, default: tuple[int, int] | None = None) -> tuple[int, int] | None:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    text = raw_value.strip()
    if text == "":
        return None
    return _parse_size(text, env_name=name)


def _normalize_profile_name(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def _read_profile_file_path() -> Path:
    raw_value = os.getenv(FACE_DETECT_PROFILE_FILE_ENV)
    if raw_value is None or raw_value.strip() == "":
        return DEFAULT_FACE_DETECT_PROFILE_FILE
    return Path(raw_value.strip()).expanduser()


def _coerce_profile_size(
    *,
    raw_value: object,
    profile_name: str,
    field_name: str,
    allow_none: bool,
) -> tuple[int, int] | None:
    if raw_value is None:
        if allow_none:
            return None
        raise ValueError(f"profile {profile_name!r} field {field_name!r} must not be null")
    if isinstance(raw_value, (list, tuple)):
        if len(raw_value) != 2:
            raise ValueError(
                f"profile {profile_name!r} field {field_name!r} must contain exactly two values"
            )
        try:
            width = int(raw_value[0])
            height = int(raw_value[1])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"profile {profile_name!r} field {field_name!r} must contain integer values"
            ) from exc
        return (width, height)
    if isinstance(raw_value, str):
        return _parse_size(raw_value, env_name=f"profile {profile_name} field {field_name}")
    raise ValueError(
        f"profile {profile_name!r} field {field_name!r} must be WIDTHxHEIGHT string or [w, h] list"
    )


def _coerce_profile_settings(
    profile_name: str,
    raw_settings: object,
) -> dict[str, object]:
    if not isinstance(raw_settings, dict):
        raise ValueError(f"profile {profile_name!r} must be a JSON object")
    required_fields = (
        "scale_factor",
        "min_neighbors",
        "min_size",
        "max_size",
        "min_area_ratio",
        "max_area_ratio",
        "aspect_ratio_min",
        "aspect_ratio_max",
    )
    missing = [field for field in required_fields if field not in raw_settings]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"profile {profile_name!r} missing required fields: {missing_list}")

    scale_factor = float(raw_settings["scale_factor"])
    min_neighbors = int(raw_settings["min_neighbors"])
    min_size = _coerce_profile_size(
        raw_value=raw_settings["min_size"],
        profile_name=profile_name,
        field_name="min_size",
        allow_none=False,
    )
    max_size = _coerce_profile_size(
        raw_value=raw_settings["max_size"],
        profile_name=profile_name,
        field_name="max_size",
        allow_none=True,
    )
    min_area_ratio = float(raw_settings["min_area_ratio"])
    max_area_ratio = float(raw_settings["max_area_ratio"])
    aspect_ratio_min = float(raw_settings["aspect_ratio_min"])
    aspect_ratio_max = float(raw_settings["aspect_ratio_max"])

    _validate_detector_params(
        scale_factor=scale_factor,
        min_neighbors=min_neighbors,
        min_size=min_size if min_size is not None else (1, 1),
        max_size=max_size,
        min_area_ratio=min_area_ratio,
        max_area_ratio=max_area_ratio,
        aspect_ratio_min=aspect_ratio_min,
        aspect_ratio_max=aspect_ratio_max,
    )

    return {
        "scale_factor": scale_factor,
        "min_neighbors": min_neighbors,
        "min_size": min_size,
        "max_size": max_size,
        "min_area_ratio": min_area_ratio,
        "max_area_ratio": max_area_ratio,
        "aspect_ratio_min": aspect_ratio_min,
        "aspect_ratio_max": aspect_ratio_max,
    }


def _load_face_detect_profiles() -> dict[str, dict[str, object]]:
    profile_file = _read_profile_file_path()
    try:
        payload = json.loads(profile_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read face-detection profile file {profile_file}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in face-detection profile file {profile_file}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"face-detection profile file {profile_file} must contain a JSON object")

    profiles: dict[str, dict[str, object]] = {}
    for raw_name, raw_settings in payload.items():
        if not isinstance(raw_name, str):
            raise ValueError(f"face-detection profile names must be strings, got {raw_name!r}")
        normalized_name = _normalize_profile_name(raw_name)
        if normalized_name == "":
            raise ValueError("face-detection profile names must not be empty")
        profiles[normalized_name] = _coerce_profile_settings(normalized_name, raw_settings)
    if not profiles:
        raise ValueError(f"face-detection profile file {profile_file} must define at least one profile")
    return profiles


def _resolve_face_detect_profile() -> tuple[str, dict[str, object]]:
    profiles = _load_face_detect_profiles()
    raw_name = os.getenv(FACE_DETECT_PROFILE_ENV, DEFAULT_FACE_DETECT_PROFILE)
    normalized_name = _normalize_profile_name(raw_name)
    if normalized_name == "":
        normalized_name = DEFAULT_FACE_DETECT_PROFILE
    canonical_name = _FACE_DETECT_PROFILE_ALIASES.get(normalized_name, normalized_name)
    profile = profiles.get(canonical_name)
    if profile is None:
        allowed_profiles = ", ".join(sorted(profiles.keys()))
        raise ValueError(
            f"{FACE_DETECT_PROFILE_ENV} must be one of {allowed_profiles}, got {raw_name!r}"
        )
    return canonical_name, profile


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
