from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


THUMBNAIL_MAX_SIZE = (256, 256)
THUMBNAIL_MIME_TYPE = "image/jpeg"


@dataclass(frozen=True)
class ThumbnailImage:
    jpeg_bytes: bytes
    mime_type: str
    width: int
    height: int


def generate_thumbnail(path: Path) -> ThumbnailImage:
    with Image.open(path) as image:
        prepared = ImageOps.exif_transpose(image)
        if prepared.mode not in ("RGB", "L"):
            prepared = prepared.convert("RGB")
        elif prepared.mode == "L":
            prepared = prepared.convert("RGB")
        prepared.thumbnail(THUMBNAIL_MAX_SIZE)

        output = BytesIO()
        prepared.save(output, format="JPEG", quality=75, optimize=True)
        return ThumbnailImage(
            jpeg_bytes=output.getvalue(),
            mime_type=THUMBNAIL_MIME_TYPE,
            width=prepared.width,
            height=prepared.height,
        )
