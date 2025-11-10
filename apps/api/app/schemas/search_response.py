from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class FaceHit(BaseModel):
    person_id: Optional[str] = None

class PhotoHit(BaseModel):
    photo_id: str
    path: str
    ext: str
    camera_make: Optional[str] = None
    orientation: Optional[str] = None
    shot_ts: str
    filesize: int
    tags: List[str] = []
    people: List[str] = []
    faces: List[FaceHit] = []
    relevance: Optional[float] = None

class Hits(BaseModel):
    total: int
    items: List[PhotoHit]
    cursor: Optional[str] = None

class SearchResponse(BaseModel):
    hits: Hits
    facets: Dict[str, Any] = {}
