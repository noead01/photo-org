import runpy

import pytest

from app.dependencies import INGEST_PROCESSOR_ROLE, WORKER_ROLE_HEADER
from app.services.worker_queue_trigger import (
    DEFAULT_INTERNAL_API_BASE_URL,
    PROCESS_QUEUE_PATH,
    QueueTriggerClient,
    _normalize_base_url,
    trigger_queue_processing,
)


def test_normalize_base_url_strips_only_trailing_slashes():
    assert _normalize_base_url("http://example.test///") == "http://example.test"
    assert _normalize_base_url("http://example.test/path") == "http://example.test/path"


def test_trigger_queue_processing_posts_to_internal_api(monkeypatch):
    calls = []

    class _Response:
        def raise_for_status(self):
            calls.append("raised")

    def fake_post(url, *, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return _Response()

    monkeypatch.setattr("app.services.worker_queue_trigger.httpx.post", fake_post)

    trigger_queue_processing(base_url="http://worker-api/", timeout=7.5, limit=17)

    assert calls == [
        (
            f"http://worker-api{PROCESS_QUEUE_PATH}",
            {WORKER_ROLE_HEADER: INGEST_PROCESSOR_ROLE},
            {"limit": 17},
            7.5,
        ),
        "raised",
    ]


def test_queue_trigger_client_uses_env_default_and_forwards_config(monkeypatch):
    calls = []

    monkeypatch.setenv("PHOTO_ORG_INTERNAL_API_BASE_URL", "http://env-api")
    monkeypatch.setattr(
        "app.services.worker_queue_trigger.trigger_queue_processing",
        lambda **kwargs: calls.append(kwargs),
    )

    client = QueueTriggerClient(timeout=9.0, limit=33)
    client.process_pending_queue()

    assert calls == [{"base_url": "http://env-api", "timeout": 9.0, "limit": 33}]


def test_queue_trigger_client_falls_back_to_builtin_default(monkeypatch):
    calls = []

    monkeypatch.delenv("PHOTO_ORG_INTERNAL_API_BASE_URL", raising=False)
    monkeypatch.setattr(
        "app.services.worker_queue_trigger.trigger_queue_processing",
        lambda **kwargs: calls.append(kwargs),
    )

    QueueTriggerClient().process_pending_queue()

    assert calls == [
        {"base_url": DEFAULT_INTERNAL_API_BASE_URL, "timeout": 5.0, "limit": 100}
    ]


def test_module_main_exits_with_cli_status(monkeypatch):
    monkeypatch.setattr("app.cli.main", lambda: 7)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("app.__main__", run_name="__main__")

    assert exc_info.value.code == 7
