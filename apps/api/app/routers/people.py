from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.people import (
    PersonInUseError,
    PersonNotFoundError,
    create_person,
    delete_person,
    get_person,
    list_people,
    update_person,
)


router = APIRouter(prefix="/people", tags=["people"])

DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    Field(...),
]


class CreatePersonRequest(BaseModel):
    """Request payload to create a person identity."""

    model_config = ConfigDict(
        json_schema_extra={"description": "Create a person by display name."}
    )

    display_name: DisplayName


class UpdatePersonRequest(BaseModel):
    """Request payload to rename an existing person identity."""

    model_config = ConfigDict(
        json_schema_extra={"description": "Rename a person by display name."}
    )

    display_name: DisplayName


class PersonResponse(BaseModel):
    """Person identity returned by people API operations."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Canonical person record with audit timestamps."
        }
    )

    person_id: str
    display_name: str
    created_ts: datetime
    updated_ts: datetime


@router.post(
    "",
    summary="Create person",
    description="Create a person identity used by face-labeling workflows.",
    response_model=PersonResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_person_endpoint(
    body: CreatePersonRequest,
    db: Session = Depends(get_db),
) -> PersonResponse:
    person = create_person(
        db.connection(),
        display_name=body.display_name,
        now=datetime.now(tz=UTC),
    )
    db.commit()
    return PersonResponse.model_validate(person)


@router.get(
    "",
    summary="List people",
    description="Return all person identities ordered by display name.",
    response_model=list[PersonResponse],
)
def list_people_endpoint(db: Session = Depends(get_db)) -> list[PersonResponse]:
    rows = list_people(db.connection())
    return [PersonResponse.model_validate(row) for row in rows]


@router.get(
    "/{person_id}",
    summary="Get person",
    description="Return one person identity by ID.",
    response_model=PersonResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Person not found",
        }
    },
)
def get_person_endpoint(
    person_id: str,
    db: Session = Depends(get_db),
) -> PersonResponse:
    person = get_person(db.connection(), person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return PersonResponse.model_validate(person)


@router.patch(
    "/{person_id}",
    summary="Update person",
    description="Rename one person identity by ID.",
    response_model=PersonResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Person not found",
        }
    },
)
def update_person_endpoint(
    person_id: str,
    body: UpdatePersonRequest,
    db: Session = Depends(get_db),
) -> PersonResponse:
    try:
        person = update_person(
            db.connection(),
            person_id=person_id,
            display_name=body.display_name,
            now=datetime.now(tz=UTC),
        )
    except PersonNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return PersonResponse.model_validate(person)


@router.delete(
    "/{person_id}",
    summary="Delete person",
    description="Delete one person identity by ID when it has no face references.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Person not found",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Person is referenced by face or label data",
        },
    },
)
def delete_person_endpoint(
    person_id: str,
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_person(db.connection(), person_id)
    except PersonNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PersonInUseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
