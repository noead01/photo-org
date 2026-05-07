from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_face_validation_role
from app.services.face_suggestion_review import (
    confirm_top_face_suggestions,
    list_unassigned_face_suggestion_photos,
)


router = APIRouter(prefix="/suggestions", tags=["suggestions"])


class SuggestionThumbnailResponse(BaseModel):
    mime_type: str
    width: int
    height: int
    data_base64: str


class TopFaceSuggestionResponse(BaseModel):
    person_id: str
    display_name: str
    confidence: float
    rank: int | None = None


class SuggestedUnassignedFaceResponse(BaseModel):
    face_id: str
    bbox_x: int | None = None
    bbox_y: int | None = None
    bbox_w: int | None = None
    bbox_h: int | None = None
    bbox_space_width: int | None = None
    bbox_space_height: int | None = None
    top_suggestion: TopFaceSuggestionResponse
    suggestions: list[TopFaceSuggestionResponse] = Field(default_factory=list)


class SuggestionReviewPhotoResponse(BaseModel):
    photo_id: str
    path: str
    thumbnail: SuggestionThumbnailResponse | None = None
    faces: list[SuggestedUnassignedFaceResponse]


class SuggestionReviewPageResponse(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class SuggestionReviewListResponse(BaseModel):
    page: SuggestionReviewPageResponse
    items: list[SuggestionReviewPhotoResponse]


class SuggestionSelectedAssignmentRequest(BaseModel):
    face_id: str
    person_id: str


class SuggestionConfirmFacesRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "description": "Confirm selected face IDs by assigning each to its current top suggestion."
        }
    )

    face_ids: list[str] = Field(default_factory=list, max_length=500)
    assignments: list[SuggestionSelectedAssignmentRequest] = Field(default_factory=list, max_length=500)


class SuggestedFaceAssignmentResponse(BaseModel):
    face_id: str
    photo_id: str
    person_id: str


class SuggestedFaceSkipResponse(BaseModel):
    face_id: str
    reason: str


class SuggestionConfirmFacesResponse(BaseModel):
    assigned: list[SuggestedFaceAssignmentResponse]
    skipped: list[SuggestedFaceSkipResponse]


@router.get(
    "/faces",
    summary="List photos with unassigned faces and top suggestions",
    description="Return a paginated suggestion-review feed of photos that contain unassigned faces with top-ranked suggestions.",
    response_model=SuggestionReviewListResponse,
)
def list_suggestion_review_faces_endpoint(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    min_confidence: Annotated[float, Query(ge=0, le=1)] = 0,
    excluded_person_ids: Annotated[list[str] | None, Query()] = None,
    db: Session = Depends(get_db),
) -> SuggestionReviewListResponse:
    result = list_unassigned_face_suggestion_photos(
        db.connection(),
        page=page,
        page_size=page_size,
        min_confidence=min_confidence,
        excluded_person_ids=excluded_person_ids,
    )
    return SuggestionReviewListResponse.model_validate(result)


@router.post(
    "/confirmations",
    summary="Confirm top suggestions for selected faces",
    description="Assign selected unassigned faces to their current top-ranked suggestions.",
    response_model=SuggestionConfirmFacesResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Face validation role required"},
    },
)
def confirm_suggestion_faces_endpoint(
    body: SuggestionConfirmFacesRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_face_validation_role),
) -> SuggestionConfirmFacesResponse:
    result = confirm_top_face_suggestions(
        db.connection(),
        face_ids=body.face_ids,
        selected_assignments=[
            {"face_id": assignment.face_id, "person_id": assignment.person_id}
            for assignment in body.assignments
        ],
    )
    db.commit()
    return SuggestionConfirmFacesResponse.model_validate(result)
