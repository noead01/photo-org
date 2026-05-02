from __future__ import annotations

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
    ) -> None:
        import cv2  # type: ignore

        self._cv2 = cv2
        self._scale_factor = scale_factor
        self._min_neighbors = min_neighbors
        self._min_size = min_size

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        classifier = cv2.CascadeClassifier(cascade_path)
        if classifier.empty():
            raise RuntimeError(f"unable to load cascade classifier at {cascade_path}")
        self._classifier = classifier

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
            boxes = self._classifier.detectMultiScale(
                grayscale,
                scaleFactor=self._scale_factor,
                minNeighbors=self._min_neighbors,
                minSize=self._min_size,
            )

            detections: list[dict] = []
            for index, (x, y, w, h) in enumerate(boxes):
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
                            "detector": "opencv-haarcascade",
                            "model": "haarcascade_frontalface_default",
                            "scale_factor": self._scale_factor,
                            "min_neighbors": self._min_neighbors,
                            "min_size": list(self._min_size),
                            "bbox_space_width": width,
                            "bbox_space_height": height,
                        },
                    ).as_row()
                )

        return detections


def _encode_jpeg(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()
