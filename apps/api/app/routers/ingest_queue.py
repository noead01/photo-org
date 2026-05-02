from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies import require_worker_role
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
