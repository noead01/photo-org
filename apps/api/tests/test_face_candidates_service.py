from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import face_candidates as face_candidates_service


class _FakeMappingsResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def first(self) -> dict[str, object] | None:
        if not self._rows:
            return None
        return self._rows[0]

    def all(self) -> list[dict[str, object]]:
        return list(self._rows)


class _FakeExecuteResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeMappingsResult:
        return _FakeMappingsResult(self._rows)


class _FakeConnection:
    def __init__(self, *, dialect_name: str, source_embedding: list[float] | None) -> None:
        self.dialect = SimpleNamespace(name=dialect_name)
        self._source_embedding = source_embedding
        self.execute_calls = 0

    def execute(self, statement):  # noqa: ANN001
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _FakeExecuteResult(
                (
                    []
                    if self._source_embedding is None
                    else [{"face_id": "source-face", "embedding": self._source_embedding}]
                )
            )
        raise AssertionError("Unexpected execute call for this fake connection")


def test_lookup_nearest_neighbor_candidates_uses_postgresql_strategy_in_isolation(monkeypatch):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.6")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.85")
    connection = _FakeConnection(dialect_name="postgresql", source_embedding=[1.0, 0.0, 0.0])
    called: dict[str, object] = {}

    def _fake_postgresql_strategy(connection_arg, *, face_id, source_embedding, limit):  # noqa: ANN001
        called["strategy"] = "postgresql"
        called["connection"] = connection_arg
        called["face_id"] = face_id
        called["source_embedding"] = source_embedding
        called["limit"] = limit
        return [
            {
                "person_id": "person-1",
                "display_name": "Alex",
                "matched_face_id": "match-face-1",
                "distance": 0.1,
            }
        ]

    def _fake_python_strategy(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Python fallback should not be used for PostgreSQL")

    monkeypatch.setattr(
        face_candidates_service,
        "_lookup_candidates_postgresql",
        _fake_postgresql_strategy,
    )
    monkeypatch.setattr(
        face_candidates_service,
        "_lookup_candidates_python",
        _fake_python_strategy,
    )

    result = face_candidates_service.lookup_nearest_neighbor_candidates(
        connection,
        face_id="source-face",
        limit=7,
    )

    assert called == {
        "strategy": "postgresql",
        "connection": connection,
        "face_id": "source-face",
        "source_embedding": [1.0, 0.0, 0.0],
        "limit": 7,
    }
    assert result == {
        "face_id": "source-face",
        "candidates": [
            {
                "person_id": "person-1",
                "display_name": "Alex",
                "matched_face_id": "match-face-1",
                "distance": 0.1,
                "confidence": 0.9,
            }
        ],
        "suggestion_policy": {
            "decision": "review_needed",
            "review_threshold": 0.6,
            "auto_accept_threshold": 0.85,
            "top_candidate_confidence": 0.9,
        },
    }


def test_lookup_nearest_neighbor_candidates_uses_python_fallback_outside_postgresql(monkeypatch):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.75")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.95")
    connection = _FakeConnection(dialect_name="sqlite", source_embedding=[1.0, 0.0, 0.0])
    called: dict[str, object] = {}

    def _fake_postgresql_strategy(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("PostgreSQL strategy should not be used for SQLite")

    def _fake_python_strategy(connection_arg, *, face_id, source_embedding):  # noqa: ANN001
        called["strategy"] = "python"
        called["connection"] = connection_arg
        called["face_id"] = face_id
        called["source_embedding"] = source_embedding
        return [
            {
                "person_id": "person-2",
                "display_name": "Blair",
                "matched_face_id": "match-face-2",
                "distance": 0.2,
            }
        ]

    monkeypatch.setattr(
        face_candidates_service,
        "_lookup_candidates_postgresql",
        _fake_postgresql_strategy,
    )
    monkeypatch.setattr(
        face_candidates_service,
        "_lookup_candidates_python",
        _fake_python_strategy,
    )

    result = face_candidates_service.lookup_nearest_neighbor_candidates(
        connection,
        face_id="source-face",
        limit=7,
    )

    assert called == {
        "strategy": "python",
        "connection": connection,
        "face_id": "source-face",
        "source_embedding": [1.0, 0.0, 0.0],
    }
    assert result == {
        "face_id": "source-face",
        "candidates": [
            {
                "person_id": "person-2",
                "display_name": "Blair",
                "matched_face_id": "match-face-2",
                "distance": 0.2,
                "confidence": 0.8,
            }
        ],
        "suggestion_policy": {
            "decision": "review_needed",
            "review_threshold": 0.75,
            "auto_accept_threshold": 0.95,
            "top_candidate_confidence": 0.8,
        },
    }


def test_lookup_nearest_neighbor_candidates_applies_no_suggestion_policy_for_low_confidence(monkeypatch):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.9")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.95")
    connection = _FakeConnection(dialect_name="sqlite", source_embedding=[1.0, 0.0, 0.0])

    def _fake_postgresql_strategy(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("PostgreSQL strategy should not be used for SQLite")

    def _fake_python_strategy(*args, **kwargs):  # noqa: ANN002, ANN003
        return [
            {
                "person_id": "person-2",
                "display_name": "Blair",
                "matched_face_id": "match-face-2",
                "distance": 0.2,
            }
        ]

    monkeypatch.setattr(
        face_candidates_service,
        "_lookup_candidates_postgresql",
        _fake_postgresql_strategy,
    )
    monkeypatch.setattr(
        face_candidates_service,
        "_lookup_candidates_python",
        _fake_python_strategy,
    )

    result = face_candidates_service.lookup_nearest_neighbor_candidates(
        connection,
        face_id="source-face",
        limit=7,
    )

    assert result == {
        "face_id": "source-face",
        "candidates": [],
        "suggestion_policy": {
            "decision": "no_suggestion",
            "review_threshold": 0.9,
            "auto_accept_threshold": 0.95,
            "top_candidate_confidence": 0.8,
        },
    }


def test_lookup_nearest_neighbor_candidates_applies_no_suggestion_for_ambiguous_top_match(monkeypatch):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.7")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.95")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_MIN_TOP_MARGIN", "0.05")
    connection = _FakeConnection(dialect_name="sqlite", source_embedding=[1.0, 0.0, 0.0])

    def _fake_postgresql_strategy(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("PostgreSQL strategy should not be used for SQLite")

    def _fake_python_strategy(*args, **kwargs):  # noqa: ANN002, ANN003
        return [
            {
                "person_id": "person-1",
                "display_name": "Alex",
                "matched_face_id": "match-face-1",
                "distance": 0.21,
            },
            {
                "person_id": "person-2",
                "display_name": "Blair",
                "matched_face_id": "match-face-2",
                "distance": 0.23,
            },
        ]

    monkeypatch.setattr(
        face_candidates_service,
        "_lookup_candidates_postgresql",
        _fake_postgresql_strategy,
    )
    monkeypatch.setattr(
        face_candidates_service,
        "_lookup_candidates_python",
        _fake_python_strategy,
    )

    result = face_candidates_service.lookup_nearest_neighbor_candidates(
        connection,
        face_id="source-face",
        limit=7,
    )

    assert result == {
        "face_id": "source-face",
        "candidates": [],
        "suggestion_policy": {
            "decision": "no_suggestion",
            "review_threshold": 0.7,
            "auto_accept_threshold": 0.95,
            "top_candidate_confidence": 0.79,
        },
    }


def test_lookup_nearest_neighbor_candidates_keeps_high_confidence_ambiguous_top_match(monkeypatch):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.7")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.9")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_MIN_TOP_MARGIN", "0.05")
    connection = _FakeConnection(dialect_name="sqlite", source_embedding=[1.0, 0.0, 0.0])

    def _fake_postgresql_strategy(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("PostgreSQL strategy should not be used for SQLite")

    def _fake_python_strategy(*args, **kwargs):  # noqa: ANN002, ANN003
        return [
            {
                "person_id": "person-1",
                "display_name": "Alex",
                "matched_face_id": "match-face-1",
                "distance": 0.07,
            },
            {
                "person_id": "person-2",
                "display_name": "Blair",
                "matched_face_id": "match-face-2",
                "distance": 0.08,
            },
        ]

    monkeypatch.setattr(
        face_candidates_service,
        "_lookup_candidates_postgresql",
        _fake_postgresql_strategy,
    )
    monkeypatch.setattr(
        face_candidates_service,
        "_lookup_candidates_python",
        _fake_python_strategy,
    )

    result = face_candidates_service.lookup_nearest_neighbor_candidates(
        connection,
        face_id="source-face",
        limit=7,
    )

    assert result["face_id"] == "source-face"
    assert [candidate["person_id"] for candidate in result["candidates"]] == ["person-1", "person-2"]
    assert [candidate["display_name"] for candidate in result["candidates"]] == ["Alex", "Blair"]
    assert [candidate["distance"] for candidate in result["candidates"]] == [0.07, 0.08]
    assert [candidate["confidence"] for candidate in result["candidates"]] == pytest.approx([0.93, 0.92], abs=1e-6)
    assert result["suggestion_policy"] == {
        "decision": "review_needed",
        "review_threshold": 0.7,
        "auto_accept_threshold": 0.9,
        "top_candidate_confidence": pytest.approx(0.93, abs=1e-6),
    }
