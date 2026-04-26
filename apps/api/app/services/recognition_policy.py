from __future__ import annotations

import math
import os


DEFAULT_REVIEW_THRESHOLD = 0.7
DEFAULT_AUTO_ACCEPT_THRESHOLD = 0.9

REVIEW_THRESHOLD_ENV = "PHOTO_ORG_RECOGNITION_REVIEW_THRESHOLD"
AUTO_ACCEPT_THRESHOLD_ENV = "PHOTO_ORG_RECOGNITION_AUTO_ACCEPT_THRESHOLD"

SUGGESTION_DECISION_AUTO_APPLY = "auto_apply"
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


def distance_to_confidence(distance: float) -> float:
    return min(1.0, max(0.0, 1.0 - float(distance)))


def classify_suggestion_confidence(
    confidence: float,
    *,
    review_threshold: float,
    auto_accept_threshold: float,
) -> str:
    bounded_confidence = min(1.0, max(0.0, confidence))
    if bounded_confidence >= auto_accept_threshold:
        return SUGGESTION_DECISION_AUTO_APPLY
    if bounded_confidence >= review_threshold:
        return SUGGESTION_DECISION_REVIEW_NEEDED
    return SUGGESTION_DECISION_NO_SUGGESTION


def _validate_threshold(label: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{label} must be within [0.0, 1.0]")
