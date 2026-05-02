from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.search_response import OriginalAvailabilityHit, ThumbnailHit


class PhotoDetailFace(BaseModel):
    """Face detection bounding box attached to a photo detail response."""

    model_config = ConfigDict(
        json_schema_extra={"description": "A single detected face and its bounding box."}
    )

    face_id: str = Field(description="Stable face identifier.")
    person_id: str | None = Field(default=None, description="Recognized person identifier.")
    bbox_x: int | None = Field(default=None, description="Bounding-box x coordinate.")
    bbox_y: int | None = Field(default=None, description="Bounding-box y coordinate.")
    bbox_w: int | None = Field(default=None, description="Bounding-box width in pixels.")
    bbox_h: int | None = Field(default=None, description="Bounding-box height in pixels.")
    bbox_space_width: int | None = Field(
        default=None,
        description="Width of the image coordinate space used to produce bounding-box coordinates.",
    )
    bbox_space_height: int | None = Field(
        default=None,
        description="Height of the image coordinate space used to produce bounding-box coordinates.",
    )
    label_source: str | None = Field(
        default=None,
        description="Latest face-label source for the current assigned person, if available.",
    )
    confidence: float | None = Field(
        default=None,
        description="Confidence for machine-produced label records, if available.",
    )
    model_version: str | None = Field(
        default=None,
        description="Model version attached to latest label provenance, if available.",
    )
    provenance: dict[str, object] | None = Field(
        default=None,
        description="Raw provenance payload for the latest matching label record.",
    )
    label_recorded_ts: str | None = Field(
        default=None,
        description="Timestamp of the latest matching label record.",
    )


class PhotoMetadataProjection(BaseModel):
    """Low-level metadata projection attached to photo details."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Canonical photo metadata, timestamps, and face counts."
        }
    )

    sha256: str = Field(description="SHA-256 digest for the original file.")
    phash: str | None = Field(default=None, description="Perceptual hash, if available.")
    shot_ts_source: str | None = Field(
        default=None,
        description="Source used to derive the shot timestamp.",
    )
    camera_model: str | None = Field(default=None, description="Camera model string.")
    software: str | None = Field(default=None, description="Software string from metadata.")
    gps_latitude: float | None = Field(default=None, description="GPS latitude in decimal degrees.")
    gps_longitude: float | None = Field(default=None, description="GPS longitude in decimal degrees.")
    gps_altitude: float | None = Field(default=None, description="GPS altitude in meters.")
    created_ts: datetime = Field(description="Creation timestamp for the catalog record.")
    updated_ts: datetime = Field(description="Last update timestamp for the catalog record.")
    modified_ts: datetime | None = Field(
        default=None,
        description="Last modified timestamp from the source file, if present.",
    )
    deleted_ts: datetime | None = Field(
        default=None,
        description="Soft-delete timestamp when the file is missing or removed.",
    )
    faces_count: int = Field(description="Number of detected faces.")
    faces_detected_ts: datetime | None = Field(
        default=None,
        description="Timestamp when face detection was last run.",
    )


class PhotoDetailResponse(BaseModel):
    """Detailed photo record including metadata and related assets."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Photo identity, rich metadata, and attached assets."
        }
    )

    photo_id: str = Field(description="Stable photo identifier.")
    path: str = Field(description="Canonical file path for the photo.")
    ext: str = Field(description="File extension for the photo.")
    camera_make: str | None = Field(default=None, description="Camera make, if available.")
    orientation: str | None = Field(default=None, description="Image orientation, if known.")
    shot_ts: str | None = Field(default=None, description="Shot timestamp as an ISO-8601 string.")
    filesize: int = Field(description="File size in bytes.")
    tags: list[str] = Field(default_factory=list, description="Assigned tag values.")
    people: list[str] = Field(default_factory=list, description="Recognized people attached to the photo.")
    faces: list[PhotoDetailFace] = Field(default_factory=list, description="Detected faces and bounding boxes.")
    thumbnail: ThumbnailHit | None = Field(
        default=None,
        description="Inline thumbnail payload, if available.",
    )
    original: OriginalAvailabilityHit | None = Field(
        default=None,
        description="Original-file availability summary, if available.",
    )
    metadata: PhotoMetadataProjection = Field(description="Canonical catalog metadata for the photo.")
