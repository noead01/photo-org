import math

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional, Literal

from app.core.enums import FilesizeRange


class DateFilter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None


class SortSpec(BaseModel):
    by: Literal["shot_ts", "relevance"] = "shot_ts"
    dir: Literal["asc", "desc"] = "desc"


class PageSpec(BaseModel):
    limit: Optional[int] = 50
    cursor: Optional[str] = None


class LocationRadiusFilter(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 50

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("latitude must be finite")
        if value < -90 or value > 90:
            raise ValueError("latitude must be between -90 and 90")
        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("longitude must be finite")
        if value < -180 or value > 180:
            raise ValueError("longitude must be between -180 and 180")
        return value

    @field_validator("radius_km")
    @classmethod
    def validate_radius_km(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("radius_km must be finite")
        if value <= 0:
            raise ValueError("radius_km must be greater than 0")
        return value


class SearchFilters(BaseModel):
    date: Optional[DateFilter] = None
    camera_make: Optional[List[str]] = None
    extension: Optional[List[str]] = None
    path_hints: Optional[List[str]] = None
    orientation: Optional[List[str]] = None
    filesize_range: Optional[FilesizeRange] = None
    has_faces: Optional[bool] = None
    tags: Optional[List[str]] = None
    people: Optional[List[str]] = None
    person_names: Optional[List[str]] = None
    person_certainty_mode: Optional[Literal["human_only", "include_suggestions"]] = None
    suggestion_confidence_min: Optional[float] = None
    location_radius: Optional[LocationRadiusFilter] = None

    @field_validator("suggestion_confidence_min")
    @classmethod
    def validate_suggestion_confidence_min(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if not math.isfinite(value):
            raise ValueError("suggestion_confidence_min must be finite")
        if value < 0 or value > 1:
            raise ValueError("suggestion_confidence_min must be between 0 and 1")
        return value


class VectorSpec(BaseModel):
    dim: int
    values: List[float]


class SearchRequest(BaseModel):
    q: Optional[str] = None
    filters: SearchFilters = SearchFilters()
    sort: SortSpec = SortSpec()
    page: PageSpec = PageSpec()
    vector: Optional[VectorSpec] = None
    similarity_k: Optional[int] = None
