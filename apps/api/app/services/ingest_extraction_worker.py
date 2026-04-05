from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.db.session import create_db_engine
from app.processing.faces import OpenCvFaceDetector
from app.processing.ingest_persistence import (
    PhotoRecord,
    build_photo_record_from_sha,
    compute_photo_sha256,
    lookup_existing_artifacts_by_sha,
    serialize_extracted_content_submission,
    serialize_reused_content_submission,
)
from app.processing.metadata import stat_timestamp_to_iso
from app.services.thumbnails import generate_thumbnail


@dataclass(frozen=True)
class ExtractionResult:
    extracted_payload: dict
    reused_existing_artifacts: bool
    analysis_performed: bool


def process_candidate_payload(
    database_url,
    *,
    payload: dict,
    face_detector=None,
) -> ExtractionResult:
    runtime_path = Path(payload["runtime_path"]).expanduser().resolve()
    sha256 = compute_photo_sha256(runtime_path)

    engine = create_db_engine(database_url)
    with engine.begin() as connection:
        existing_artifacts = lookup_existing_artifacts_by_sha(connection, sha256)

    if existing_artifacts is not None:
        reused_record = _build_reused_photo_record(
            runtime_path,
            canonical_path=payload["canonical_path"],
            sha256=sha256,
            existing_artifacts=existing_artifacts,
        )
        return ExtractionResult(
            extracted_payload=serialize_reused_content_submission(
                record=reused_record,
                candidate_payload=payload,
                warnings=[],
                detections=existing_artifacts["detections"],
            ),
            reused_existing_artifacts=True,
            analysis_performed=False,
        )

    record = build_photo_record_from_sha(
        runtime_path,
        canonical_path=payload["canonical_path"],
        sha256=sha256,
    )

    thumbnail = generate_thumbnail(runtime_path)
    detector = face_detector if face_detector is not None else OpenCvFaceDetector()
    detections = detector.detect(runtime_path)
    extracted_record = PhotoRecord(
        **{
            **record.__dict__,
            "thumbnail_jpeg": thumbnail.jpeg_bytes,
            "thumbnail_mime_type": thumbnail.mime_type,
            "thumbnail_width": thumbnail.width,
            "thumbnail_height": thumbnail.height,
            "faces_count": len(detections),
        }
    )
    return ExtractionResult(
        extracted_payload=serialize_extracted_content_submission(
            record=extracted_record,
            storage_source_id=payload["storage_source_id"],
            watched_folder_id=payload["watched_folder_id"],
            relative_path=payload["relative_path"],
            detections=detections,
            warnings=[],
        ),
        reused_existing_artifacts=False,
        analysis_performed=True,
    )


__all__ = ["ExtractionResult", "process_candidate_payload"]


def _build_reused_photo_record(
    path: Path,
    *,
    canonical_path: str,
    sha256: str,
    existing_artifacts: dict[str, object | None],
) -> PhotoRecord:
    stat = path.stat()
    return PhotoRecord(
        photo_id=str(uuid5(NAMESPACE_URL, f"{canonical_path}:{sha256}")),
        path=canonical_path,
        sha256=sha256,
        filesize=stat.st_size,
        ext=path.suffix.lower().lstrip("."),
        created_ts=_parse_datetime(stat_timestamp_to_iso(stat.st_ctime)),
        modified_ts=_parse_datetime(stat_timestamp_to_iso(stat.st_mtime)),
        shot_ts=_parse_optional_datetime(existing_artifacts.get("shot_ts")),
        shot_ts_source=existing_artifacts.get("shot_ts_source"),
        camera_make=existing_artifacts.get("camera_make"),
        camera_model=existing_artifacts.get("camera_model"),
        software=existing_artifacts.get("software"),
        orientation=existing_artifacts.get("orientation"),
        gps_latitude=existing_artifacts.get("gps_latitude"),
        gps_longitude=existing_artifacts.get("gps_longitude"),
        gps_altitude=existing_artifacts.get("gps_altitude"),
        thumbnail_jpeg=existing_artifacts["thumbnail_jpeg"],
        thumbnail_mime_type=existing_artifacts["thumbnail_mime_type"],
        thumbnail_width=existing_artifacts["thumbnail_width"],
        thumbnail_height=existing_artifacts["thumbnail_height"],
        faces_count=int(existing_artifacts["faces_count"] or 0),
    )


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _parse_optional_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    return _parse_datetime(value)
