from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.repositories.photos_repo import PhotosRepository


router = APIRouter(prefix="/exports", tags=["exports"])


class ExportPhotosRequest(BaseModel):
    photo_ids: list[str] = Field(min_length=1)


def _normalize_photo_ids(photo_ids: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in photo_ids:
        normalized = raw.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _safe_archive_name(photo_id: str, resolved_path: Path) -> str:
    name = resolved_path.name.strip()
    if not name:
        name = f"{photo_id}.bin"
    return f"{photo_id}_{name}"


@router.post(
    "/photos",
    summary="Export selected photos",
    description="Bundle selected original photo files into a ZIP archive.",
    responses={
        status.HTTP_200_OK: {
            "content": {
                "application/zip": {},
            }
        }
    },
)
def export_photos_endpoint(body: ExportPhotosRequest, db: Session = Depends(get_db)) -> Response:
    normalized_photo_ids = _normalize_photo_ids(body.photo_ids)
    if not normalized_photo_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No valid photo IDs.")

    repo = PhotosRepository(db)
    output = io.BytesIO()
    exported_count = 0
    skipped_count = 0

    with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
        for photo_id in normalized_photo_ids:
            resolved_path = repo.resolve_original_photo_path(photo_id)
            if resolved_path is None or not resolved_path.is_file():
                skipped_count += 1
                continue

            archive.write(resolved_path, arcname=_safe_archive_name(photo_id, resolved_path))
            exported_count += 1

    if exported_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="None of the requested photos could be exported.",
        )

    output.seek(0)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    filename = f"photo-org-export-{timestamp}.zip"

    return Response(
        content=output.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Photo-Org-Exported-Count": str(exported_count),
            "X-Photo-Org-Skipped-Count": str(skipped_count),
        },
    )
