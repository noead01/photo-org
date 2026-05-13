from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_worker_role
from app.services.face_embedding_backfill import (
    FaceEmbeddingModelUnavailableError,
    reembed_missing_face_embeddings,
)
from app.services.face_suggestions import refresh_stale_unassigned_face_suggestions
from app.services.ingest_queue_processor import process_pending_ingest_queue
from app.services.storage_source_polling import trigger_storage_source_polling


router = APIRouter(tags=["internal-ingest-queue"])
FACE_SUGGESTION_RECOMPUTE_PAYLOAD_TYPE = "face_suggestion_recompute"


class ProcessQueueRequest(BaseModel):
    """Request payload for worker-driven ingest queue processing."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Limit how many pending ingest items to process in one call."
        }
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Maximum number of pending queue items to process.",
    )


class ProcessQueueResponse(BaseModel):
    """Aggregate result returned after queue processing."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Counts of processed items, failures, and retryable errors."
        }
    )

    processed: int = Field(description="Number of items processed successfully.")
    failed: int = Field(description="Number of items that failed permanently.")
    retryable_errors: int = Field(description="Number of items that can be retried.")


class TriggerStorageSourcePollingRequest(BaseModel):
    """Request payload for polling watched folders and draining the ingest queue."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": (
                "Trigger a storage-source poll and process queued ingest work until "
                "no additional items are completed."
            )
        }
    )

    queue_process_limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum queue items to process per internal drain pass.",
    )
    drain_queue: bool = Field(
        default=True,
        description="When false, only scan and enqueue candidates without draining queued ingest work.",
    )


class TriggerStorageSourcePollingResponse(BaseModel):
    """Aggregate outcome for a storage-source poll plus queue processing."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Polling and queue-processing totals for one trigger request."
        }
    )

    scanned: int = Field(description="Number of photos scanned across enabled watched folders.")
    enqueued: int = Field(description="Number of ingest candidates enqueued by polling.")
    inserted: int = Field(description="Number of new photo rows inserted after queue processing.")
    updated: int = Field(description="Number of existing photo rows updated by polling.")
    processed: int = Field(description="Number of queued items processed successfully.")
    failed: int = Field(description="Number of queue items marked as permanent failures.")
    retryable_errors: int = Field(description="Number of queue items marked retryable.")
    error_count: int = Field(description="Combined count of poll and queue processing errors.")
    poll_errors: list[str] = Field(description="Detailed poll-time errors from watched-folder scans.")


class ReembedMissingFaceEmbeddingsRequest(BaseModel):
    """Request payload for worker-driven face embedding backfill."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": (
                "Backfill embeddings for face rows that are missing vectors, using the configured "
                "SFace model."
            )
        }
    )

    limit: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum missing-embedding face rows to scan in one call.",
    )
    refresh_related: bool = Field(
        default=True,
        description=(
            "When true, refresh person representations and face suggestions for people impacted "
            "by updated embeddings."
        ),
    )
    suggestion_limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Suggestion depth to use when refreshing impacted person scopes.",
    )


class ReembedMissingFaceEmbeddingsResponse(BaseModel):
    """Aggregate result returned after face embedding backfill."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": (
                "Counts of scanned rows, embedding updates, skips, and related refresh activity."
            )
        }
    )

    scanned: int
    updated: int
    skipped_missing_bitmap: int
    skipped_extraction_failed: int
    refreshed_people: int
    refreshed_suggestion_scopes: int


class RefreshStaleFaceSuggestionsRequest(BaseModel):
    """Request payload for stale/uncomputed unassigned face-suggestion refresh."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": (
                "Recompute suggestions for unassigned faces with missing snapshots or "
                "snapshots older than the provided staleness threshold."
            )
        }
    )

    stale_after_minutes: int = Field(
        default=24 * 60,
        ge=0,
        le=60 * 24 * 30,
        description=(
            "Face suggestions older than this threshold (minutes) are considered stale."
        ),
    )
    face_limit: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Maximum number of unassigned faces to refresh in one call.",
    )
    suggestion_limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Suggestion depth to persist per refreshed face.",
    )


class RefreshStaleFaceSuggestionsResponse(BaseModel):
    stale_after_minutes: int
    suggestion_limit: int
    requested_face_limit: int
    refreshed_face_count: int
    stale_cutoff_ts: str


@router.post(
    "/internal/ingest-queue/process",
    summary="Process ingest queue",
    description="Claim and process pending ingest queue items for the worker process.",
    response_model=ProcessQueueResponse,
    responses={403: {"description": "Worker role required"}},
)
def process_ingest_queue_endpoint(
    body: ProcessQueueRequest = Body(default_factory=ProcessQueueRequest),
    _: None = Depends(require_worker_role),
) -> ProcessQueueResponse:
    result = process_pending_ingest_queue(limit=body.limit)
    return ProcessQueueResponse(
        processed=result.processed,
        failed=result.failed,
        retryable_errors=result.retryable_errors,
    )


@router.post(
    "/internal/face-suggestions/recompute/process",
    summary="Process face suggestion recompute queue",
    description=(
        "Claim and process pending face suggestion recompute queue items only."
    ),
    response_model=ProcessQueueResponse,
    responses={403: {"description": "Worker role required"}},
)
def process_face_suggestion_recompute_queue_endpoint(
    body: ProcessQueueRequest = Body(default_factory=ProcessQueueRequest),
    _: None = Depends(require_worker_role),
) -> ProcessQueueResponse:
    result = process_pending_ingest_queue(
        limit=body.limit,
        payload_types={FACE_SUGGESTION_RECOMPUTE_PAYLOAD_TYPE},
    )
    return ProcessQueueResponse(
        processed=result.processed,
        failed=result.failed,
        retryable_errors=result.retryable_errors,
    )


@router.post(
    "/internal/face-suggestions/recompute/stale",
    summary="Recompute stale unassigned face suggestions",
    description=(
        "Refresh suggestions for unassigned faces that have never been assessed or "
        "whose persisted suggestions are older than a configurable age."
    ),
    response_model=RefreshStaleFaceSuggestionsResponse,
    responses={403: {"description": "Worker role required"}},
)
def recompute_stale_unassigned_face_suggestions_endpoint(
    body: RefreshStaleFaceSuggestionsRequest = Body(
        default_factory=RefreshStaleFaceSuggestionsRequest
    ),
    _: None = Depends(require_worker_role),
    db: Session = Depends(get_db),
) -> RefreshStaleFaceSuggestionsResponse:
    result = refresh_stale_unassigned_face_suggestions(
        db.connection(),
        stale_after_minutes=body.stale_after_minutes,
        face_limit=body.face_limit,
        suggestion_limit=body.suggestion_limit,
    )
    db.commit()
    return RefreshStaleFaceSuggestionsResponse(
        stale_after_minutes=result.stale_after_minutes,
        suggestion_limit=result.suggestion_limit,
        requested_face_limit=result.requested_face_limit,
        refreshed_face_count=result.refreshed_face_count,
        stale_cutoff_ts=result.stale_cutoff_ts.isoformat(),
    )


@router.post(
    "/internal/storage-sources/poll",
    summary="Poll storage sources",
    description=(
        "Trigger polling for enabled storage-source watched folders and process queued ingest items."
    ),
    response_model=TriggerStorageSourcePollingResponse,
    responses={403: {"description": "Worker role required"}},
)
def poll_storage_sources_endpoint(
    body: TriggerStorageSourcePollingRequest = Body(
        default_factory=TriggerStorageSourcePollingRequest
    ),
    _: None = Depends(require_worker_role),
) -> TriggerStorageSourcePollingResponse:
    result = trigger_storage_source_polling(
        queue_process_limit=body.queue_process_limit,
        drain_queue=body.drain_queue,
    )
    return TriggerStorageSourcePollingResponse(
        scanned=result.scanned,
        enqueued=result.enqueued,
        inserted=result.inserted,
        updated=result.updated,
        processed=result.queue_processed,
        failed=result.queue_failed,
        retryable_errors=result.queue_retryable_errors,
        error_count=result.error_count,
        poll_errors=list(result.poll_errors),
    )


@router.post(
    "/internal/faces/reembed-missing-embeddings",
    summary="Re-embed missing face embeddings",
    description=(
        "Backfill face embeddings from persisted face crops for rows missing embeddings, then "
        "optionally refresh related person representations and suggestions."
    ),
    response_model=ReembedMissingFaceEmbeddingsResponse,
    responses={
        403: {"description": "Worker role required"},
        409: {"description": "Face embedding model not configured or unavailable"},
    },
)
def reembed_missing_face_embeddings_endpoint(
    body: ReembedMissingFaceEmbeddingsRequest = Body(
        default_factory=ReembedMissingFaceEmbeddingsRequest
    ),
    _: None = Depends(require_worker_role),
    db: Session = Depends(get_db),
) -> ReembedMissingFaceEmbeddingsResponse:
    try:
        result = reembed_missing_face_embeddings(
            db.connection(),
            limit=body.limit,
            refresh_related=body.refresh_related,
            suggestion_limit=body.suggestion_limit,
        )
    except FaceEmbeddingModelUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.commit()
    return ReembedMissingFaceEmbeddingsResponse.model_validate(result)
