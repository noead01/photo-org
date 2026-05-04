from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_worker_role
from app.services.face_embedding_backfill import (
    FaceEmbeddingModelUnavailableError,
    reembed_missing_face_embeddings,
)
from app.services.ingest_queue_processor import process_pending_ingest_queue
from app.services.storage_source_polling import trigger_storage_source_polling


router = APIRouter(tags=["internal-ingest-queue"])


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
        le=1000,
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
    result = trigger_storage_source_polling(queue_process_limit=body.queue_process_limit)
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
