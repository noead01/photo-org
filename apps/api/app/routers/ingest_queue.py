from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies import require_worker_role
from app.services.ingest_queue_processor import process_pending_ingest_queue


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
