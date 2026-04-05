from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.operational_activity import (
    InvalidOperationalActivityCursor,
    get_operational_activity,
    get_operational_activity_history,
)


router = APIRouter(prefix="/operations", tags=["operations"])


class PollingLiveItemResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "A currently active watched-folder polling run."}
    )

    ingest_run_id: str
    watched_folder_id: str
    storage_source_id: str
    display_name: str | None = None
    scan_path: str
    started_ts: datetime
    files_seen: int | None = None
    estimated_files_total: int | None = None
    percent_complete: float | None = None


class PollingLiveSummaryResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "Summary of active polling work."}
    )

    active_count: int
    files_seen: int | None = None
    estimated_files_total: int | None = None
    percent_complete: float | None = None


class PollingLiveSectionResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "Currently active polling work."}
    )

    items: list[PollingLiveItemResponse]
    summary: PollingLiveSummaryResponse


class QueueLiveItemResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "A currently active ingest queue item."}
    )

    ingest_queue_id: str
    payload_type: str
    path: str | None = None
    last_attempt_ts: datetime | None = None
    is_stalled: bool
    processed_count: int | None = None
    estimated_total: int | None = None
    percent_complete: float | None = None


class QueueLiveSummaryResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "Summary of active ingest queue work."}
    )

    pending_count: int
    processing_count: int
    stalled_count: int
    processed_count: int | None = None
    estimated_total: int | None = None
    percent_complete: float | None = None


class QueueLiveSectionResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "Currently active ingest queue work."}
    )

    items: list[QueueLiveItemResponse]
    summary: QueueLiveSummaryResponse


class OperationalActivityLiveResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "Live operational activity snapshot for active work."}
    )

    observed_at: datetime
    polling: PollingLiveSectionResponse
    ingest_queue: QueueLiveSectionResponse


class PollingHistoryItemResponse(BaseModel):
    ingest_run_id: str
    watched_folder_id: str
    display_name: str | None = None
    event_type: str
    event_ts: datetime
    status: str
    error_summary: str | None = None


class QueueHistoryItemResponse(BaseModel):
    ingest_queue_id: str
    payload_type: str
    path: str | None = None
    event_type: str
    event_ts: datetime
    status: str
    last_error: str | None = None


class PagedPollingHistorySectionResponse(BaseModel):
    items: list[PollingHistoryItemResponse]
    next_cursor: str | None = None
    has_more: bool


class PagedQueueHistorySectionResponse(BaseModel):
    items: list[QueueHistoryItemResponse]
    next_cursor: str | None = None
    has_more: bool


class OperationalActivityHistoryResponse(BaseModel):
    polling: PagedPollingHistorySectionResponse
    ingest_queue: PagedQueueHistorySectionResponse


@router.get(
    "/activity",
    summary="Get live operational activity",
    description=(
        "Return a read-only snapshot of currently active polling and ingest queue work "
        "for repeated operator polling."
    ),
    response_model=OperationalActivityLiveResponse,
)
def get_operational_activity_endpoint(
    db: Session = Depends(get_db),
) -> OperationalActivityLiveResponse:
    payload = get_operational_activity(db.connection())
    return OperationalActivityLiveResponse.model_validate(payload)


@router.get(
    "/activity/history",
    summary="Get operational activity history",
    response_model=OperationalActivityHistoryResponse,
)
def get_operational_activity_history_endpoint(
    polling_limit: int = 20,
    polling_cursor: str | None = None,
    queue_limit: int = 20,
    queue_cursor: str | None = None,
    db: Session = Depends(get_db),
) -> OperationalActivityHistoryResponse:
    try:
        payload = get_operational_activity_history(
            db.connection(),
            polling_limit=polling_limit,
            polling_cursor=polling_cursor,
            queue_limit=queue_limit,
            queue_cursor=queue_cursor,
        )
    except InvalidOperationalActivityCursor as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {exc}") from exc
    return OperationalActivityHistoryResponse.model_validate(payload)
