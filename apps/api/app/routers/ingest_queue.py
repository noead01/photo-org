from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from app.dependencies import require_worker_role
from app.services.ingest_queue_processor import process_pending_ingest_queue


router = APIRouter(tags=["internal-ingest-queue"])


class ProcessQueueRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)


class ProcessQueueResponse(BaseModel):
    processed: int
    failed: int
    retryable_errors: int


@router.post("/internal/ingest-queue/process", response_model=ProcessQueueResponse)
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
