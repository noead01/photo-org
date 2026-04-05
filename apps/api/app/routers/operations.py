from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.operational_activity import get_operational_activity


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
