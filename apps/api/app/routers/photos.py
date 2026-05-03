from __future__ import annotations

import io
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.repositories.photos_repo import PhotosRepository
from app.schemas.photo_response import PhotoDetailResponse
from app.schemas.search_response import PhotoHit


router = APIRouter(prefix="/photos", tags=["photos"])
_TRANSCODE_EXTENSIONS = {".heic", ".heif"}
_TRANSCODE_MIME_TYPES = {
    "image/heic",
    "image/heif",
    "image/heic-sequence",
    "image/heif-sequence",
}


@router.get(
    "",
    summary="List photos",
    description="Return searchable photo hits from the catalog.",
    response_model=list[PhotoHit],
)
def list_photos(db: Session = Depends(get_db)) -> list[PhotoHit]:
    repo = PhotosRepository(db)
    return [PhotoHit(**item) for item in repo.list_photos()]


@router.get(
    "/{photo_id}",
    summary="Get photo detail",
    description="Return the full photo record, including metadata and availability details.",
    response_model=PhotoDetailResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Photo not found"}},
)
def get_photo_detail(photo_id: str, db: Session = Depends(get_db)) -> PhotoDetailResponse:
    repo = PhotosRepository(db)
    photo = repo.get_photo_detail(photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return PhotoDetailResponse.model_validate(photo)


def _iter_file_chunks(path: Path, chunk_size: int = 1024 * 1024):
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            yield chunk


def _needs_browser_transcode(path: Path, mime_type: str | None) -> bool:
    if path.suffix.lower() in _TRANSCODE_EXTENSIONS:
        return True
    if mime_type is None:
        return False
    return mime_type.lower() in _TRANSCODE_MIME_TYPES


def _transcode_image_to_jpeg(path: Path) -> bytes:
    from PIL import Image, ImageOps  # type: ignore
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
    with Image.open(path) as image:
        prepared = ImageOps.exif_transpose(image)
        if prepared.mode not in ("RGB", "L"):
            prepared = prepared.convert("RGB")
        elif prepared.mode == "L":
            prepared = prepared.convert("RGB")
        buffer = io.BytesIO()
        prepared.save(buffer, format="JPEG", quality=95, optimize=True)
        return buffer.getvalue()


@router.get(
    "/{photo_id}/original",
    summary="Get photo original",
    description="Stream the original photo file when storage aliases and source markers resolve to a readable file.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Original photo file not found"},
    },
)
def get_photo_original(
    photo_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    repo = PhotosRepository(db)
    resolved = repo.resolve_original_photo_path(photo_id)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original photo not found")

    mime_type, _ = mimetypes.guess_type(str(resolved))
    content_type = mime_type or "application/octet-stream"
    if _needs_browser_transcode(resolved, mime_type):
        try:
            jpeg_bytes = _transcode_image_to_jpeg(resolved)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Original photo could not be transcoded for browser preview: {exc}",
            ) from exc
        return StreamingResponse(
            io.BytesIO(jpeg_bytes),
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f'inline; filename="{resolved.stem}.jpg"',
            },
        )

    # Some browsers request image bytes with Range and can fail to decode
    # partial payloads for photo previews. Serve full-image responses here.
    if "range" in request.headers:
        return StreamingResponse(
            _iter_file_chunks(resolved),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{resolved.name}"',
            },
        )

    return FileResponse(
        path=resolved,
        media_type=content_type,
        filename=resolved.name,
        content_disposition_type="inline",
    )
