from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.operational_activity import get_operational_activity


router = APIRouter(prefix="/operations", tags=["operations"])


class ActiveWatchedFolderResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "description": "Watched folder currently associated with an in-progress polling run."
        }
    )

    watched_folder_id: str
    storage_source_id: str
    display_name: str | None = None
    scan_path: str
    started_ts: datetime | None = None


class PollingActivityResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "Current watched-folder polling activity."}
    )

    active_count: int = Field(description="Number of watched folders with an active polling run.")
    active_watched_folders: list[ActiveWatchedFolderResponse]


class IngestQueueActivityResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "Current queue backlog and processing summary."}
    )

    pending_count: int
    processing_count: int
    failed_count: int
    stalled_count: int
    lease_timeout_seconds: int
    oldest_pending_ts: datetime | None = None


class ActivitySignalsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "Operator-facing warning signals derived from current state."}
    )

    recent_failure_count: int
    stalled_count: int


class RecentFailureResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "Recent ingest failure surfaced for operator troubleshooting."}
    )

    kind: str
    watched_folder_id: str
    display_name: str | None = None
    status: str
    error_summary: str | None = None
    completed_ts: datetime | None = None


class OperationalActivityResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "description": "Read-only operational summary for polling and ingest queue activity."
        }
    )

    state: str = Field(description="High-level operator state: idle, polling, processing_queue, or attention_required.")
    observed_at: datetime
    polling: PollingActivityResponse
    ingest_queue: IngestQueueActivityResponse
    signals: ActivitySignalsResponse
    recent_failures: list[RecentFailureResponse]


@router.get(
    "/activity",
    summary="Get operational activity",
    description=(
        "Return a read-only summary of current polling activity, queue backlog, and recent failure signals "
        "so operators can tell whether the system is idle, busy, or needs attention."
    ),
    response_model=OperationalActivityResponse,
)
def get_operational_activity_endpoint(
    db: Session = Depends(get_db),
) -> OperationalActivityResponse:
    payload = get_operational_activity(db.connection())
    return OperationalActivityResponse.model_validate(payload)
