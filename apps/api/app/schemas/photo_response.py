from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.search_response import OriginalAvailabilityHit, ThumbnailHit


class PhotoDetailFace(BaseModel):
    person_id: str | None = None
    bbox_x: int | None = None
    bbox_y: int | None = None
    bbox_w: int | None = None
    bbox_h: int | None = None


class PhotoMetadataProjection(BaseModel):
    sha256: str
    phash: str | None = None
    shot_ts_source: str | None = None
    camera_model: str | None = None
    software: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    gps_altitude: float | None = None
    created_ts: datetime
    updated_ts: datetime
    modified_ts: datetime | None = None
    deleted_ts: datetime | None = None
    faces_count: int
    faces_detected_ts: datetime | None = None


class PhotoDetailResponse(BaseModel):
    photo_id: str
    path: str
    ext: str
    camera_make: str | None = None
    orientation: str | None = None
    shot_ts: str
    filesize: int
    tags: list[str] = []
    people: list[str] = []
    faces: list[PhotoDetailFace] = []
    thumbnail: ThumbnailHit | None = None
    original: OriginalAvailabilityHit | None = None
    metadata: PhotoMetadataProjection
