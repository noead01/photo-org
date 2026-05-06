from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_face_validation_role
from app.services.face_assignment import (
    FaceAlreadyAssignedError,
    FaceAlreadyDismissedError,
    FaceAlreadyAssignedToPersonError,
    FaceAssignedToDifferentPersonError,
    FaceNotAssignedError,
    FaceNotFoundError,
    PersonNotFoundError,
    confirm_face_assignment,
    dismiss_false_positive_face,
    record_review_needed_face_suggestion,
    assign_face_to_person,
    reassign_face_to_person,
)
from app.services.face_candidates import (
    FaceNotFoundError as FaceCandidateNotFoundError,
    lookup_nearest_neighbor_candidates,
)
from app.services.face_suggestions import persist_face_suggestions_from_live_candidates
from app.services.recognition_policy import (
    resolve_prediction_metadata,
    SUGGESTION_DECISION_REVIEW_NEEDED,
)


router = APIRouter(prefix="/faces", tags=["face-labeling"])

PersonId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    Field(...),
]


class AssignFaceRequest(BaseModel):
    """Request payload to assign one detected face to one person."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Assign an unlabeled face to an existing person identity."
        }
    )

    person_id: PersonId


class FaceAssignmentResponse(BaseModel):
    """Assignment result for one face and one person."""

    model_config = ConfigDict(
        json_schema_extra={"description": "Resolved face-to-person assignment details."}
    )

    face_id: str
    photo_id: str
    person_id: str


class FaceCorrectionResponse(BaseModel):
    """Correction result for one face reassigned to a different person."""

    model_config = ConfigDict(
        json_schema_extra={"description": "Resolved face reassignment details."}
    )

    face_id: str
    photo_id: str
    previous_person_id: str
    person_id: str


class FaceConfirmationResponse(BaseModel):
    """Confirmation result for one face assignment."""

    model_config = ConfigDict(
        json_schema_extra={"description": "Resolved face assignment confirmation details."}
    )

    face_id: str
    photo_id: str
    person_id: str


class FaceDismissalResponse(BaseModel):
    """Dismissal result for one face detected as a false positive."""

    model_config = ConfigDict(
        json_schema_extra={"description": "Resolved face dismissal details."}
    )

    face_id: str
    photo_id: str
    dismissed_ts: str


class FaceCandidateResponse(BaseModel):
    """Nearest-neighbor candidate details for one person identity."""

    model_config = ConfigDict(
        json_schema_extra={"description": "One candidate identity ranked for a source face."}
    )

    person_id: str
    display_name: str
    matched_face_id: str
    distance: float
    confidence: float


class ReviewNeededFaceSuggestionResponse(BaseModel):
    """Review-needed suggestion details for medium-confidence matches."""

    face_id: str
    photo_id: str
    person_id: str
    confidence: float
    matched_face_id: str


class FaceSuggestionPolicyResponse(BaseModel):
    """Threshold policy decision for the source face suggestion flow."""

    decision: Literal["review_needed", "no_suggestion"]
    review_threshold: float
    auto_accept_threshold: float
    top_candidate_confidence: float | None


class FaceCandidateLookupResponse(BaseModel):
    """Nearest-neighbor candidate lookup result for one source face."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Top person candidates computed from nearest face-embedding neighbors."
        }
    )

    face_id: str
    candidates: list[FaceCandidateResponse]
    suggestion_policy: FaceSuggestionPolicyResponse
    review_needed_suggestion: ReviewNeededFaceSuggestionResponse | None = None


@router.post(
    "/{face_id}/assignments",
    summary="Assign face to person",
    description="Assign an unlabeled face to a person identity.",
    response_model=FaceAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Face validation role required"},
        status.HTTP_404_NOT_FOUND: {"description": "Face or person not found"},
        status.HTTP_409_CONFLICT: {"description": "Face already assigned"},
    },
)
def assign_face_to_person_endpoint(
    face_id: str,
    body: AssignFaceRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_face_validation_role),
) -> FaceAssignmentResponse:
    try:
        assignment = assign_face_to_person(
            db.connection(),
            face_id=face_id,
            person_id=body.person_id,
        )
    except FaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PersonNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FaceAlreadyAssignedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.commit()
    return FaceAssignmentResponse.model_validate(assignment)


@router.post(
    "/{face_id}/corrections",
    summary="Correct face assignment",
    description="Reassign an already-labeled face to a different person identity.",
    response_model=FaceCorrectionResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Face validation role required"},
        status.HTTP_404_NOT_FOUND: {"description": "Face or person not found"},
        status.HTTP_409_CONFLICT: {
            "description": "Face is unassigned or already assigned to the requested person"
        },
    },
)
def correct_face_assignment_endpoint(
    face_id: str,
    body: AssignFaceRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_face_validation_role),
) -> FaceCorrectionResponse:
    try:
        correction = reassign_face_to_person(
            db.connection(),
            face_id=face_id,
            person_id=body.person_id,
        )
    except FaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PersonNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FaceNotAssignedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FaceAlreadyAssignedToPersonError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FaceAlreadyAssignedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.commit()
    return FaceCorrectionResponse.model_validate(correction)


@router.post(
    "/{face_id}/confirmations",
    summary="Confirm face assignment",
    description="Confirm an existing face assignment for the same person identity.",
    response_model=FaceConfirmationResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Face validation role required"},
        status.HTTP_404_NOT_FOUND: {"description": "Face or person not found"},
        status.HTTP_409_CONFLICT: {
            "description": "Face is unassigned or assigned to a different person"
        },
    },
)
def confirm_face_assignment_endpoint(
    face_id: str,
    body: AssignFaceRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_face_validation_role),
) -> FaceConfirmationResponse:
    try:
        confirmation = confirm_face_assignment(
            db.connection(),
            face_id=face_id,
            person_id=body.person_id,
        )
    except FaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PersonNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FaceNotAssignedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FaceAssignedToDifferentPersonError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.commit()
    return FaceConfirmationResponse.model_validate(confirmation)


@router.post(
    "/{face_id}/dismissals",
    summary="Dismiss false-positive face detection",
    description="Persistently dismiss an unassigned detected face that does not correspond to a real face.",
    response_model=FaceDismissalResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Face validation role required"},
        status.HTTP_404_NOT_FOUND: {"description": "Face not found"},
        status.HTTP_409_CONFLICT: {"description": "Face already assigned or already dismissed"},
    },
)
def dismiss_face_endpoint(
    face_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_face_validation_role),
) -> FaceDismissalResponse:
    try:
        dismissal = dismiss_false_positive_face(
            db.connection(),
            face_id=face_id,
        )
    except FaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FaceAlreadyAssignedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FaceAlreadyDismissedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.commit()
    return FaceDismissalResponse.model_validate(dismissal)


@router.get(
    "/{face_id}/candidates",
    summary="Lookup nearest person candidates",
    description="Return nearest labeled people candidates for the requested face embedding.",
    response_model=FaceCandidateLookupResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Face not found"},
    },
)
def lookup_face_candidates_endpoint(
    face_id: str,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    enforce_min_confidence: bool = Query(
        default=True,
        description="When false, return nearest candidates even if suggestion policy resolves to no_suggestion.",
    ),
    db: Session = Depends(get_db),
) -> FaceCandidateLookupResponse:
    try:
        result = lookup_nearest_neighbor_candidates(
            db.connection(),
            face_id=face_id,
            limit=limit,
            enforce_min_confidence=enforce_min_confidence,
        )
    except FaceCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    suggestion_policy = result["suggestion_policy"]
    candidates = result["candidates"]
    prediction_metadata = resolve_prediction_metadata()
    persisted_snapshot_count = persist_face_suggestions_from_live_candidates(
        db.connection(),
        face_id=face_id,
        candidates=candidates if isinstance(candidates, list) else [],
        model_version=prediction_metadata["model_version"],
        limit=limit,
    )
    did_commit = persisted_snapshot_count >= 0
    if (
        suggestion_policy["decision"] == SUGGESTION_DECISION_REVIEW_NEEDED
        and isinstance(candidates, list)
        and candidates
    ):
        top_candidate = candidates[0]
        review_needed_suggestion = record_review_needed_face_suggestion(
            db.connection(),
            face_id=face_id,
            person_id=str(top_candidate["person_id"]),
            confidence=float(top_candidate["confidence"]),
            distance=float(top_candidate["distance"]),
            matched_face_id=str(top_candidate["matched_face_id"]),
            review_threshold=float(suggestion_policy["review_threshold"]),
            auto_accept_threshold=float(suggestion_policy["auto_accept_threshold"]),
        )
        if review_needed_suggestion is not None:
            result["review_needed_suggestion"] = review_needed_suggestion
            did_commit = True

    if did_commit:
        db.commit()

    return FaceCandidateLookupResponse.model_validate(result)
