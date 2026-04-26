from __future__ import annotations

import pytest

from app.services.recognition_policy import (
    classify_suggestion_confidence,
    distance_to_confidence,
    resolve_prediction_metadata,
    resolve_suggestion_thresholds,
)


def test_resolve_suggestion_thresholds_reads_environment_overrides(monkeypatch):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.7")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.9")

    thresholds = resolve_suggestion_thresholds()

    assert thresholds == {"review_threshold": 0.7, "auto_accept_threshold": 0.9}


def test_resolve_suggestion_thresholds_rejects_invalid_range(monkeypatch):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD", "0.9")
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD", "0.8")

    with pytest.raises(ValueError, match="auto accept threshold must be greater than or equal to review threshold"):
        resolve_suggestion_thresholds()


@pytest.mark.parametrize(
    ("distance", "expected"),
    [
        (0.2, 0.8),
        (1.2, 0.0),
        (-0.2, 1.0),
    ],
)
def test_distance_to_confidence_clamps_into_zero_to_one(distance: float, expected: float):
    assert distance_to_confidence(distance) == pytest.approx(expected, abs=1e-6)


def test_classify_suggestion_confidence_supports_three_policy_bands():
    assert classify_suggestion_confidence(0.95, review_threshold=0.7, auto_accept_threshold=0.9) == "auto_apply"
    assert classify_suggestion_confidence(0.8, review_threshold=0.7, auto_accept_threshold=0.9) == "review_needed"
    assert classify_suggestion_confidence(0.6, review_threshold=0.7, auto_accept_threshold=0.9) == "no_suggestion"


def test_resolve_prediction_metadata_reads_environment_model_version(monkeypatch):
    monkeypatch.setenv("PHOTO_ORG_RECOGNITION_MODEL_VERSION", "  facenet-v3.2  ")

    metadata = resolve_prediction_metadata()

    assert metadata == {
        "model_version": "facenet-v3.2",
        "prediction_source": "nearest-neighbor",
        "distance_metric": "cosine",
    }


def test_resolve_prediction_metadata_uses_default_model_version(monkeypatch):
    monkeypatch.delenv("PHOTO_ORG_RECOGNITION_MODEL_VERSION", raising=False)

    metadata = resolve_prediction_metadata()

    assert metadata == {
        "model_version": "nearest-neighbor-cosine-v1",
        "prediction_source": "nearest-neighbor",
        "distance_metric": "cosine",
    }
