from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class FaceHit(BaseModel):
    person_id: Optional[str] = None
    label_source: Optional[str] = None
    confidence: Optional[float] = None
    suggestions: List[Dict[str, Any]] = []


class ThumbnailHit(BaseModel):
    mime_type: str
    width: int
    height: int
    data_base64: str


class OriginalAvailabilityHit(BaseModel):
    is_available: bool
    availability_state: str
    last_failure_reason: Optional[str] = None


class PhotoHit(BaseModel):
    photo_id: str
    path: str
    ext: str
    camera_make: Optional[str] = None
    orientation: Optional[str] = None
    shot_ts: Optional[str] = None
    filesize: int
    tags: List[str] = []
    people: List[str] = []
    faces: List[FaceHit] = []
    thumbnail: Optional[ThumbnailHit] = None
    original: Optional[OriginalAvailabilityHit] = None
    relevance: Optional[float] = None


class Hits(BaseModel):
    total: int
    items: List[PhotoHit]
    cursor: Optional[str] = None


class SearchResponse(BaseModel):
    hits: Hits
    facets: Dict[str, Any] = {}
