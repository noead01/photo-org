from __future__ import annotations

import app.services.storage_source_polling as polling_service


def test_trigger_storage_source_polling_runs_poll_then_drains_queue(monkeypatch):
    queue_limits: list[int] = []
    queue_results = iter(
        [
            type("QueueResult", (), {"processed": 2, "failed": 1, "retryable_errors": 0})(),
            type("QueueResult", (), {"processed": 1, "failed": 0, "retryable_errors": 1})(),
            type("QueueResult", (), {"processed": 0, "failed": 0, "retryable_errors": 0})(),
        ]
    )
    photo_counts = iter([11, 14])

    monkeypatch.setattr(
        polling_service,
        "poll_registered_storage_sources",
        lambda **_: type(
            "PollResult",
            (),
            {
                "scanned": 12,
                "enqueued": 8,
                "updated": 5,
                "errors": ["marker mismatch"],
            },
        )(),
    )
    monkeypatch.setattr(
        polling_service,
        "process_pending_ingest_queue",
        lambda **kwargs: queue_limits.append(kwargs["limit"]) or next(queue_results),
    )
    monkeypatch.setattr(
        polling_service,
        "_count_photos",
        lambda database_url=None: next(photo_counts),
    )

    result = polling_service.trigger_storage_source_polling(queue_process_limit=77)

    assert queue_limits == [77, 77, 77]
    assert result.scanned == 12
    assert result.enqueued == 8
    assert result.inserted == 3
    assert result.updated == 5
    assert result.queue_processed == 3
    assert result.queue_failed == 1
    assert result.queue_retryable_errors == 1
    assert result.poll_errors == ("marker mismatch",)
    assert result.error_count == 3
