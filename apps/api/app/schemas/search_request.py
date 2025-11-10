from pydantic import BaseModel, Field
from typing import List, Optional, Literal

from app.core.enums import FilesizeRange

class DateFilter(BaseModel):
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None

class SortSpec(BaseModel):
    by: Literal["shot_ts", "relevance"] = "shot_ts"
    dir: Literal["asc", "desc"] = "desc"

class PageSpec(BaseModel):
    limit: Optional[int] = 50
    cursor: Optional[str] = None

class SearchFilters(BaseModel):
    date: Optional[DateFilter] = None
    camera_make: Optional[List[str]] = None
    extension: Optional[List[str]] = None
    orientation: Optional[List[str]] = None
    filesize_range: Optional[FilesizeRange] = None
    has_faces: Optional[bool] = None
    tags: Optional[List[str]] = None
    people: Optional[List[str]] = None

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
