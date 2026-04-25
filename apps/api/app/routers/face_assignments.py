from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.face_assignment import (
    FaceAlreadyAssignedError,
    FaceNotFoundError,
    PersonNotFoundError,
    assign_face_to_person,
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


@router.post(
    "/{face_id}/assignments",
    summary="Assign face to person",
    description="Assign an unlabeled face to a person identity.",
    response_model=FaceAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Face or person not found"},
        status.HTTP_409_CONFLICT: {"description": "Face already assigned"},
    },
)
def assign_face_to_person_endpoint(
    face_id: str,
    body: AssignFaceRequest,
    db: Session = Depends(get_db),
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
