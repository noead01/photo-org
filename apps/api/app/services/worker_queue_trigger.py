from __future__ import annotations

import os

import httpx

from app.dependencies import INGEST_PROCESSOR_ROLE, WORKER_ROLE_HEADER


DEFAULT_INTERNAL_API_BASE_URL = "http://127.0.0.1:8000"
PROCESS_QUEUE_PATH = "/api/v1/internal/ingest-queue/process"


class QueueTriggerClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 5.0,
        limit: int = 100,
    ) -> None:
        self._base_url = base_url or os.getenv(
            "PHOTO_ORG_INTERNAL_API_BASE_URL",
            DEFAULT_INTERNAL_API_BASE_URL,
        )
        self._timeout = timeout
        self._limit = limit

    def process_pending_queue(self) -> None:
        trigger_queue_processing(
            base_url=self._base_url,
            timeout=self._timeout,
            limit=self._limit,
        )


def trigger_queue_processing(
    *,
    base_url: str | None = None,
    timeout: float = 5.0,
    limit: int = 100,
) -> None:
    endpoint = _normalize_base_url(
        base_url
        or os.getenv("PHOTO_ORG_INTERNAL_API_BASE_URL", DEFAULT_INTERNAL_API_BASE_URL)
    )
    response = httpx.post(
        f"{endpoint}{PROCESS_QUEUE_PATH}",
        headers={WORKER_ROLE_HEADER: INGEST_PROCESSOR_ROLE},
        json={"limit": limit},
        timeout=timeout,
    )
    response.raise_for_status()


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")
