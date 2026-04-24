from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.people import create_person, get_person, list_people


router = APIRouter(prefix="/people", tags=["people"])

DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    Field(...),
]


class CreatePersonRequest(BaseModel):
    display_name: DisplayName


class PersonResponse(BaseModel):
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
