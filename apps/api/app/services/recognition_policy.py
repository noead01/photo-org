from __future__ import annotations

import math
import os


DEFAULT_REVIEW_THRESHOLD = 0.7
DEFAULT_AUTO_ACCEPT_THRESHOLD = 0.9

REVIEW_THRESHOLD_ENV = "PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD"
AUTO_ACCEPT_THRESHOLD_ENV = "PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD"
MODEL_VERSION_ENV = "PHOTO_ORG_RECOGNITION_MODEL_VERSION"

DEFAULT_MODEL_VERSION = "nearest-neighbor-cosine-v1"
PREDICTION_SOURCE_NEAREST_NEIGHBOR = "nearest-neighbor"
DISTANCE_METRIC_COSINE = "cosine"

SUGGESTION_DECISION_REVIEW_NEEDED = "review_needed"
SUGGESTION_DECISION_NO_SUGGESTION = "no_suggestion"


def resolve_suggestion_thresholds(
    *,
    review_threshold: float | None = None,
    auto_accept_threshold: float | None = None,
) -> dict[str, float]:
    if review_threshold is None:
        review_threshold = float(os.getenv(REVIEW_THRESHOLD_ENV, str(DEFAULT_REVIEW_THRESHOLD)))
    if auto_accept_threshold is None:
        auto_accept_threshold = float(
            os.getenv(
                AUTO_ACCEPT_THRESHOLD_ENV,
                str(DEFAULT_AUTO_ACCEPT_THRESHOLD),
            )
        )

    _validate_threshold("review threshold", review_threshold)
    _validate_threshold("auto accept threshold", auto_accept_threshold)
    if auto_accept_threshold < review_threshold:
        raise ValueError("auto accept threshold must be greater than or equal to review threshold")

    return {
        "review_threshold": review_threshold,
        "auto_accept_threshold": auto_accept_threshold,
    }


def resolve_prediction_metadata(
    *,
    model_version: str | None = None,
) -> dict[str, str]:
    if model_version is None:
        model_version = os.getenv(MODEL_VERSION_ENV, DEFAULT_MODEL_VERSION)
    normalized_model_version = model_version.strip()
    if not normalized_model_version:
        raise ValueError("recognition model version must be non-empty")
    return {
        "model_version": normalized_model_version,
        "prediction_source": PREDICTION_SOURCE_NEAREST_NEIGHBOR,
        "distance_metric": DISTANCE_METRIC_COSINE,
    }


def distance_to_confidence(distance: float) -> float:
    return min(1.0, max(0.0, 1.0 - float(distance)))


def classify_suggestion_confidence(
    confidence: float,
    *,
    review_threshold: float,
    auto_accept_threshold: float,
) -> str:
    del auto_accept_threshold
    bounded_confidence = min(1.0, max(0.0, confidence))
    if bounded_confidence >= review_threshold:
        return SUGGESTION_DECISION_REVIEW_NEEDED
    return SUGGESTION_DECISION_NO_SUGGESTION


def _validate_threshold(label: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{label} must be within [0.0, 1.0]")
