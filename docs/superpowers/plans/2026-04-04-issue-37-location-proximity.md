# Issue 37 Location Proximity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add coordinate-based proximity filtering to the search API with schema-level validation, a default `radius_km` of `50`, and repository filtering that excludes non-geotagged photos.

**Architecture:** Extend the existing typed search request contract with a `location_radius` object and let Pydantic reject invalid inputs at the API boundary. Then update the repository query builder to compose a distance predicate with the current `AND` filter semantics, and lock the behavior with focused search tests before changing implementation.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, pytest, SQLite-backed repository tests

---

## File Map

- Modify: `apps/api/app/schemas/search_request.py`
  Responsibility: define the public search request contract and validation rules.
- Modify: `apps/api/app/repositories/photos_repo.py`
  Responsibility: build the search query and apply typed filters, including GPS radius filtering.
- Modify: `apps/api/tests/test_search_service.py`
  Responsibility: cover schema validation, service pass-through, and repository search behavior for the geo filter.

### Task 1: Add the failing schema tests for `location_radius`

**Files:**
- Modify: `apps/api/tests/test_search_service.py`
- Test: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write the failing tests for default radius and invalid input**

```python
class TestSearchRequestLocationRadiusValidation:
    def test_location_radius_defaults_radius_km_to_50(self):
        request = SearchRequest(
            filters=SearchFilters(
                location_radius={"latitude": 48.8566, "longitude": 2.3522}
            )
        )

        assert request.filters.location_radius is not None
        assert request.filters.location_radius.radius_km == 50

    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            (
                {"latitude": 120.0, "longitude": 2.3522, "radius_km": 10},
                "latitude must be between -90 and 90",
            ),
            (
                {"latitude": 48.8566, "longitude": 200.0, "radius_km": 10},
                "longitude must be between -180 and 180",
            ),
            (
                {"latitude": 48.8566, "longitude": 2.3522, "radius_km": 0},
                "radius_km must be greater than 0",
            ),
        ],
    )
    def test_location_radius_rejects_invalid_values(self, payload, message):
        with pytest.raises(ValueError, match=message):
            SearchFilters(location_radius=payload)
```

- [ ] **Step 2: Run the new schema tests to verify they fail**

Run: `uv run python -m pytest apps/api/tests/test_search_service.py -k location_radius_validation -q`
Expected: FAIL because `SearchFilters` does not yet define `location_radius` or its validation rules.

- [ ] **Step 3: Add the minimal schema types and validation**

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocationRadiusFilter(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 50

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("latitude must be between -90 and 90")
        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("longitude must be between -180 and 180")
        return value

    @field_validator("radius_km")
    @classmethod
    def validate_radius(cls, value: float) -> float:
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
    location_radius: Optional[LocationRadiusFilter] = None
```

- [ ] **Step 4: Run the schema tests to verify they pass**

Run: `uv run python -m pytest apps/api/tests/test_search_service.py -k location_radius_validation -q`
Expected: PASS

- [ ] **Step 5: Commit the schema validation checkpoint**

```bash
git add apps/api/app/schemas/search_request.py apps/api/tests/test_search_service.py
git commit -m "feat(api): validate location radius search filters"
```

### Task 2: Add the failing service pass-through test

**Files:**
- Modify: `apps/api/tests/test_search_service.py`
- Test: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write the failing service test that passes the typed geo filter through**

```python
def test_given_location_radius_when_executing_search_then_passes_filter_to_repository(self):
    mock_repo = Mock()
    service = SearchService(repo=mock_repo)

    mock_repo.search_photos.return_value = ([], 0, None)
    mock_repo.get_filtered_photo_ids.return_value = []
    mock_repo.compute_facets.return_value = {}

    filters = SearchFilters(
        location_radius={"latitude": 48.8566, "longitude": 2.3522}
    )
    request = SearchRequest(filters=filters, sort=SortSpec(), page=PageSpec(limit=50))

    service.execute(request)

    mock_repo.search_photos.assert_called_once_with(
        filters=filters,
        sort=request.sort,
        page=request.page,
        text_query=None,
    )
    mock_repo.get_filtered_photo_ids.assert_called_once_with(filters, None)
```

- [ ] **Step 2: Run the pass-through test to verify it fails for the right reason**

Run: `uv run python -m pytest apps/api/tests/test_search_service.py -k passes_filter_to_repository -q`
Expected: FAIL before the schema work lands, or PASS immediately after Task 1 because no service changes are required.

- [ ] **Step 3: Keep the implementation minimal**

```python
class SearchService:
    def execute(self, req: SearchRequest) -> SearchResponse:
        items, total, next_cursor = self.repo.search_photos(
            filters=req.filters,
            sort=req.sort,
            page=req.page,
            text_query=req.q,
        )
        filtered_photo_ids = self.repo.get_filtered_photo_ids(req.filters, req.q)
        facets = self.repo.compute_facets(filtered_photo_ids)
        return SearchResponse(
            hits=Hits(total=total, items=[PhotoHit(**item) for item in items], cursor=next_cursor),
            facets=facets,
        )
```

- [ ] **Step 4: Run the pass-through test to confirm the current service still passes**

Run: `uv run python -m pytest apps/api/tests/test_search_service.py -k passes_filter_to_repository -q`
Expected: PASS

- [ ] **Step 5: Commit the test coverage checkpoint**

```bash
git add apps/api/tests/test_search_service.py
git commit -m "test(api): cover location radius search service pass-through"
```

### Task 3: Add the failing repository behavior tests

**Files:**
- Modify: `apps/api/tests/test_search_service.py`
- Test: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write failing repository tests for default radius, explicit radius, null GPS exclusion, and filter composition**

```python
def test_search_repository_filters_by_location_radius(self, tmp_path):
    database_url = f"sqlite:///{tmp_path / 'search-location-radius.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 4, 4, tzinfo=UTC)

    with engine.begin() as connection:
        connection.execute(
            insert(photos),
            [
                {
                    "photo_id": "near-photo",
                    "path": "travel/paris/near-photo.jpg",
                    "sha256": "1" * 64,
                    "phash": None,
                    "filesize": 100,
                    "ext": "jpg",
                    "created_ts": now,
                    "modified_ts": now,
                    "shot_ts": now,
                    "shot_ts_source": "exif",
                    "camera_make": "Canon",
                    "camera_model": None,
                    "software": None,
                    "orientation": None,
                    "gps_latitude": 48.8570,
                    "gps_longitude": 2.3500,
                    "gps_altitude": None,
                    "updated_ts": now,
                    "deleted_ts": None,
                    "faces_count": 0,
                    "faces_detected_ts": None,
                    "thumbnail_jpeg": None,
                    "thumbnail_mime_type": None,
                    "thumbnail_width": None,
                    "thumbnail_height": None,
                },
                {
                    "photo_id": "far-photo",
                    "path": "travel/lyon/far-photo.jpg",
                    "sha256": "2" * 64,
                    "phash": None,
                    "filesize": 100,
                    "ext": "jpg",
                    "created_ts": now,
                    "modified_ts": now,
                    "shot_ts": now,
                    "shot_ts_source": "exif",
                    "camera_make": "Canon",
                    "camera_model": None,
                    "software": None,
                    "orientation": None,
                    "gps_latitude": 45.7640,
                    "gps_longitude": 4.8357,
                    "gps_altitude": None,
                    "updated_ts": now,
                    "deleted_ts": None,
                    "faces_count": 0,
                    "faces_detected_ts": None,
                    "thumbnail_jpeg": None,
                    "thumbnail_mime_type": None,
                    "thumbnail_width": None,
                    "thumbnail_height": None,
                },
                {
                    "photo_id": "no-gps-photo",
                    "path": "travel/paris/no-gps-photo.jpg",
                    "sha256": "3" * 64,
                    "phash": None,
                    "filesize": 100,
                    "ext": "jpg",
                    "created_ts": now,
                    "modified_ts": now,
                    "shot_ts": now,
                    "shot_ts_source": "exif",
                    "camera_make": "Canon",
                    "camera_model": None,
                    "software": None,
                    "orientation": None,
                    "gps_latitude": None,
                    "gps_longitude": None,
                    "gps_altitude": None,
                    "updated_ts": now,
                    "deleted_ts": None,
                    "faces_count": 0,
                    "faces_detected_ts": None,
                    "thumbnail_jpeg": None,
                    "thumbnail_mime_type": None,
                    "thumbnail_width": None,
                    "thumbnail_height": None,
                },
            ],
        )

    with Session(engine) as session:
        repo = PhotosRepository(session)
        items, total, _ = repo.search_photos(
            filters=SearchFilters(
                location_radius={"latitude": 48.8566, "longitude": 2.3522, "radius_km": 5}
            ),
            sort=SortSpec(by="shot_ts", dir="desc"),
            page=PageSpec(limit=50),
        )

    assert total == 1
    assert [item["photo_id"] for item in items] == ["near-photo"]
```

- [ ] **Step 2: Run the repository tests to verify they fail before implementation**

Run: `uv run python -m pytest apps/api/tests/test_search_service.py -k location_radius -q`
Expected: FAIL because the repository does not yet apply a geo-distance predicate.

- [ ] **Step 3: Implement the minimal repository geo filter**

```python
from sqlalchemy import and_, func, or_, select


EARTH_RADIUS_KM = 6371.0


if filters.location_radius:
    latitude = filters.location_radius.latitude
    longitude = filters.location_radius.longitude
    radius_km = filters.location_radius.radius_km
    lat_radians = func.radians(self.photos.c.gps_latitude)
    lon_radians = func.radians(self.photos.c.gps_longitude)
    target_lat_radians = func.radians(latitude)
    target_lon_radians = func.radians(longitude)

    distance_km = EARTH_RADIUS_KM * func.acos(
        func.min(
            1.0,
            func.max(
                -1.0,
                func.sin(lat_radians) * func.sin(target_lat_radians)
                + func.cos(lat_radians)
                * func.cos(target_lat_radians)
                * func.cos(lon_radians - target_lon_radians),
            ),
        )
    )

    where_conditions.extend(
        [
            self.photos.c.gps_latitude.is_not(None),
            self.photos.c.gps_longitude.is_not(None),
            distance_km <= radius_km,
        ]
    )
```

- [ ] **Step 4: Run the repository tests to verify they pass**

Run: `uv run python -m pytest apps/api/tests/test_search_service.py -k location_radius -q`
Expected: PASS

- [ ] **Step 5: Commit the repository behavior checkpoint**

```bash
git add apps/api/app/repositories/photos_repo.py apps/api/tests/test_search_service.py
git commit -m "feat(api): add location radius search filtering"
```

### Task 4: Run the relevant regression slice and finish

**Files:**
- Modify: `apps/api/app/schemas/search_request.py`
- Modify: `apps/api/app/repositories/photos_repo.py`
- Modify: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Run the focused search suite**

Run: `uv run python -m pytest apps/api/tests/test_search_service.py -q`
Expected: PASS

- [ ] **Step 2: Run the repo baseline check**

Run: `make test`
Expected: PASS with the existing schema, migration, ingest, and search-adjacent verification still green.

- [ ] **Step 3: Inspect the final diff**

Run: `git diff --stat HEAD~3..HEAD`
Expected: shows the schema, repository, and search test updates only.

- [ ] **Step 4: Create the final implementation commit if the work was squashed during execution**

```bash
git add apps/api/app/schemas/search_request.py apps/api/app/repositories/photos_repo.py apps/api/tests/test_search_service.py
git commit -m "feat(api): implement location proximity search"
```

- [ ] **Step 5: Prepare branch handoff**

```bash
git status --short
git log --oneline -5
```

Expected: clean working tree and a short, reviewable commit stack for issue `#37`.
