from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_face_validation_role
from app.services.face_assignment import (
    FaceAlreadyAssignedError,
    FaceAlreadyAssignedToPersonError,
    FaceNotAssignedError,
    FaceNotFoundError,
    PersonNotFoundError,
    assign_face_to_person,
    reassign_face_to_person,
)
from app.services.face_candidates import (
    FaceEmbeddingNotAvailableError,
    FaceNotFoundError as FaceCandidateNotFoundError,
    lookup_nearest_neighbor_candidates,
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


class FaceCandidateResponse(BaseModel):
    """Nearest-neighbor candidate details for one person identity."""

    model_config = ConfigDict(
        json_schema_extra={"description": "One candidate identity ranked for a source face."}
    )

    person_id: str
    display_name: str
    matched_face_id: str
    distance: float


class FaceCandidateLookupResponse(BaseModel):
    """Nearest-neighbor candidate lookup result for one source face."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Top person candidates computed from nearest face-embedding neighbors."
        }
    )

    face_id: str
    candidates: list[FaceCandidateResponse]


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


@router.get(
    "/{face_id}/candidates",
    summary="Lookup nearest person candidates",
    description="Return nearest labeled people candidates for the requested face embedding.",
    response_model=FaceCandidateLookupResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Face not found"},
        status.HTTP_409_CONFLICT: {"description": "Face embedding not available"},
    },
)
def lookup_face_candidates_endpoint(
    face_id: str,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    db: Session = Depends(get_db),
) -> FaceCandidateLookupResponse:
    try:
        result = lookup_nearest_neighbor_candidates(
            db.connection(),
            face_id=face_id,
            limit=limit,
        )
    except FaceCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FaceEmbeddingNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return FaceCandidateLookupResponse.model_validate(result)
