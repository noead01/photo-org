"""
Unit tests for SearchService using proper dependency injection.

Tests the business logic orchestration layer that coordinates between
the repository and facet computation services.
"""

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from app.migrations import upgrade_database
from app.repositories.photos_repo import PhotosRepository
from app.services.search_service import SearchService
from app.schemas.search_request import SearchRequest, SearchFilters, SortSpec, PageSpec, DateFilter
from app.schemas.search_response import SearchResponse, Hits, PhotoHit
from app.core.enums import FilesizeRange
from app.storage import (
    faces,
    people,
    photo_files,
    photo_tags,
    photos,
    storage_sources,
    watched_folders,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_CORPUS_DIR = REPO_ROOT / "seed-corpus"
SEED_CORPUS_MANIFEST_PATH = SEED_CORPUS_DIR / "manifest.json"
SEARCH_FIXTURES_PATH = SEED_CORPUS_DIR / "search-fixtures.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_seed_manifest() -> dict:
    return _load_json(SEED_CORPUS_MANIFEST_PATH)


def _load_search_fixtures() -> list[dict]:
    data = _load_json(SEARCH_FIXTURES_PATH)
    assert isinstance(data, dict)
    fixtures = data["fixtures"]
    assert isinstance(fixtures, list)
    return fixtures


def _fixture_scenarios_for_parametrize() -> list[dict]:
    if not SEARCH_FIXTURES_PATH.exists():
        return []
    return _load_search_fixtures()


def _asset_id_by_manifest_path() -> dict[str, str]:
    return {
        asset["path"]: asset["asset_id"]
        for asset in _load_seed_manifest()["assets"]
    }


def _seed_search_fixture_catalog(connection) -> None:
    manifest = _load_seed_manifest()
    now = datetime(2026, 3, 29, tzinfo=UTC)

    connection.execute(
        insert(storage_sources).values(
            storage_source_id="seed-source",
            display_name="Seed Corpus",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            availability_state="active",
            last_failure_reason=None,
            last_validated_ts=now,
            created_ts=now,
            updated_ts=now,
        )
    )
    connection.execute(
        insert(watched_folders).values(
            watched_folder_id="seed-watched-folder",
            scan_path=str(SEED_CORPUS_DIR),
            storage_source_id="seed-source",
            relative_path=".",
            display_name="Seed Corpus",
            is_enabled=1,
            availability_state="active",
            last_failure_reason=None,
            last_successful_scan_ts=now,
            created_ts=now,
            updated_ts=now,
        )
    )

    photo_rows = []
    photo_file_rows = []
    face_rows = []
    tag_rows = []

    for index, asset in enumerate(manifest["assets"], start=1):
        asset_id = asset["asset_id"]
        expected = asset["expected"]
        manifest_path = asset["path"]
        relative_path = manifest_path.removeprefix("seed-corpus/")
        shot_ts = expected.get("shot_ts")
        parsed_shot_ts = datetime.fromisoformat(shot_ts) if shot_ts else None
        photo_id = f"photo-{asset_id}"

        photo_rows.append(
            {
                "photo_id": photo_id,
                "path": manifest_path,
                "sha256": f"{index:064x}",
                "phash": None,
                "filesize": expected["filesize_bytes"],
                "ext": expected["format"],
                "created_ts": now,
                "modified_ts": now,
                "shot_ts": parsed_shot_ts,
                "shot_ts_source": "seed-manifest" if parsed_shot_ts else None,
                "camera_make": expected.get("camera_make"),
                "camera_model": expected.get("camera_model"),
                "software": None,
                "orientation": None,
                "gps_latitude": None,
                "gps_longitude": None,
                "gps_altitude": None,
                "updated_ts": now,
                "deleted_ts": None,
                "faces_count": 1 if expected["has_faces"] else 0,
                "faces_detected_ts": now if expected["has_faces"] else None,
            }
        )
        photo_file_rows.append(
            {
                "photo_file_id": f"photo-file-{asset_id}",
                "photo_id": photo_id,
                "watched_folder_id": "seed-watched-folder",
                "relative_path": relative_path,
                "filename": Path(relative_path).name,
                "extension": expected["format"],
                "filesize": expected["filesize_bytes"],
                "created_ts": now,
                "modified_ts": now,
                "first_seen_ts": now,
                "last_seen_ts": now,
                "missing_ts": None,
                "deleted_ts": None,
                "lifecycle_state": "active",
                "absence_reason": None,
            }
        )

        if expected["has_faces"]:
            face_rows.append(
                {
                    "face_id": f"face-{asset_id}",
                    "photo_id": photo_id,
                    "person_id": None,
                    "bbox_x": 0,
                    "bbox_y": 0,
                    "bbox_w": 10,
                    "bbox_h": 10,
                    "bitmap": None,
                    "embedding": None,
                    "detector_name": "seed-fixture",
                    "detector_version": "1",
                    "provenance": None,
                    "created_ts": now,
                }
            )

        for tag in asset.get("scenario_tags", []):
            tag_rows.append({"photo_id": photo_id, "tag": tag})

    connection.execute(insert(photos), photo_rows)
    connection.execute(insert(photo_files), photo_file_rows)
    if face_rows:
        connection.execute(insert(faces), face_rows)
    if tag_rows:
        connection.execute(insert(photo_tags), tag_rows)


class TestSearchServiceExecution:
    """Test the main search execution workflow."""

    def test_given_search_request_when_executing_search_then_returns_complete_response(self):
        """Given a search request, when executing search, then returns complete SearchResponse."""
        # Given
        mock_repo = Mock()
        service = SearchService(repo=mock_repo)
        
        # Mock repository responses
        mock_items = [
            {
                "photo_id": "IMG_001", "path": "/photos/IMG_001.jpg", "ext": "jpg",
                "filesize": 2048000, "shot_ts": "2020-07-15T14:30:00",
                "camera_make": "Apple", "tags": [], "people": [], "faces": []
            },
            {
                "photo_id": "IMG_002", "path": "/photos/IMG_002.heic", "ext": "heic", 
                "filesize": 1536000, "shot_ts": "2020-07-16T10:15:00",
                "camera_make": "Apple", "tags": [], "people": [], "faces": []
            }
        ]
        mock_repo.search_photos.return_value = (mock_items, 100, "cursor123")
        mock_repo.get_filtered_photo_ids.return_value = ["photo1", "photo2", "photo3"]
        
        # Mock facet computation
        mock_repo.compute_facets.return_value = {
            "date": {"years": [{"year": 2020, "count": 2}]},
            "tags": {"vacation": 1, "beach": 1},
            "people": {},
            "duplicates": {"exact": 0, "near": 0}
        }
        
        request = SearchRequest(
            filters=SearchFilters(),
            sort=SortSpec(by="shot_ts", dir="desc"),
            page=PageSpec(limit=50)
        )
        
        # When
        response = service.execute(request)
        
        # Then
        assert isinstance(response, SearchResponse)
        assert response.hits.total == 100
        assert len(response.hits.items) == 2
        assert response.hits.cursor == "cursor123"
        assert response.facets["date"]["years"][0]["year"] == 2020
        
        # Verify repository calls
        mock_repo.search_photos.assert_called_once_with(
            filters=request.filters,
            sort=request.sort,
            page=request.page,
            text_query=None
        )
        mock_repo.get_filtered_photo_ids.assert_called_once_with(request.filters, None)

    def test_given_search_request_with_text_query_when_executing_then_passes_text_query_to_repository(self):
        """Given search request with text query, when executing, then passes text query to repository."""
        # Given
        mock_repo = Mock()
        service = SearchService(repo=mock_repo)
        
        mock_repo.search_photos.return_value = ([], 0, None)
        mock_repo.get_filtered_photo_ids.return_value = []
        mock_repo.compute_facets.return_value = {}
        
        request = SearchRequest(
            q="hawaii beach",
            filters=SearchFilters(),
            sort=SortSpec(by="shot_ts", dir="desc"),
            page=PageSpec(limit=50)
        )
        
        # When
        service.execute(request)
        
        # Then
        mock_repo.search_photos.assert_called_once_with(
            filters=request.filters,
            sort=request.sort,
            page=request.page,
            text_query="hawaii beach"
        )
        mock_repo.get_filtered_photo_ids.assert_called_once_with(request.filters, "hawaii beach")

    def test_given_complex_filters_when_executing_search_then_passes_all_filters_to_repository(self):
        """Given complex filters, when executing search, then passes all filters to repository."""
        # Given
        mock_repo = Mock()
        service = SearchService(repo=mock_repo)
        
        mock_repo.search_photos.return_value = ([], 0, None)
        mock_repo.get_filtered_photo_ids.return_value = []
        mock_repo.compute_facets.return_value = {}
        
        filters = SearchFilters(
            date=DateFilter(from_="2020-01-01", to="2020-12-31"),
            camera_make=["Apple", "Canon"],
            extension=["jpg", "heic"],
            has_faces=True,
            tags=["vacation", "beach"],
            people=["person_john", "person_jane"],
            filesize_range=FilesizeRange.medium  # Single value, not list
        )
        
        request = SearchRequest(
            q="hawaii beach",
            filters=filters,
            sort=SortSpec(by="relevance", dir="desc"),
            page=PageSpec(limit=25, cursor="abc123")
        )
        
        # When
        service.execute(request)
        
        # Then
        mock_repo.search_photos.assert_called_once_with(
            filters=filters,
            sort=request.sort,
            page=request.page,
            text_query="hawaii beach"
        )
        mock_repo.get_filtered_photo_ids.assert_called_once_with(request.filters, "hawaii beach")

    def test_given_path_hints_when_executing_search_then_passes_path_hints_to_repository(self):
        """Given path hints, when executing search, then passes them through in typed filters."""
        mock_repo = Mock()
        service = SearchService(repo=mock_repo)

        mock_repo.search_photos.return_value = ([], 0, None)
        mock_repo.get_filtered_photo_ids.return_value = []
        mock_repo.compute_facets.return_value = {}

        filters = SearchFilters(path_hints=["lake-weekend", "travel"])
        assert filters.model_dump().get("path_hints") == ["lake-weekend", "travel"]
        request = SearchRequest(
            filters=filters,
            sort=SortSpec(by="shot_ts", dir="desc"),
            page=PageSpec(limit=50),
        )

        service.execute(request)

        mock_repo.search_photos.assert_called_once_with(
            filters=filters,
            sort=request.sort,
            page=request.page,
            text_query=None,
        )
        mock_repo.get_filtered_photo_ids.assert_called_once_with(filters, None)

    def test_given_person_names_when_executing_search_then_passes_person_names_to_repository(self):
        mock_repo = Mock()
        service = SearchService(repo=mock_repo)

        mock_repo.search_photos.return_value = ([], 0, None)
        mock_repo.get_filtered_photo_ids.return_value = []
        mock_repo.compute_facets.return_value = {}

        filters = SearchFilters(person_names=["inez", "grandma"])
        assert filters.model_dump().get("person_names") == ["inez", "grandma"]
        request = SearchRequest(
            filters=filters,
            sort=SortSpec(by="shot_ts", dir="desc"),
            page=PageSpec(limit=50),
        )

        service.execute(request)

        mock_repo.search_photos.assert_called_once_with(
            filters=filters,
            sort=request.sort,
            page=request.page,
            text_query=None,
        )
        mock_repo.get_filtered_photo_ids.assert_called_once_with(filters, None)

    def test_given_empty_results_when_executing_search_then_returns_empty_response_with_facets(self):
        """Given empty results, when executing search, then returns empty response with facets."""
        # Given
        mock_repo = Mock()
        service = SearchService(repo=mock_repo)
        
        mock_repo.search_photos.return_value = ([], 0, None)
        mock_repo.get_filtered_photo_ids.return_value = []
        mock_repo.compute_facets.return_value = {
            "date": {"years": []},
            "tags": {},
            "people": {},
            "duplicates": {"exact": 0, "near": 0}
        }
        
        request = SearchRequest(
            filters=SearchFilters(),
            sort=SortSpec(by="shot_ts", dir="desc"),
            page=PageSpec(limit=50)
        )
        
        # When
        response = service.execute(request)
        
        # Then
        assert response.hits.total == 0
        assert len(response.hits.items) == 0
        assert response.hits.cursor is None
        assert response.facets["date"]["years"] == []
        assert response.facets["duplicates"]["exact"] == 0


class TestSearchServiceFacetComputation:
    """Test facet computation coordination."""

    def test_given_filtered_photo_ids_when_computing_facets_then_calls_repository_compute_facets(self):
        """Given filtered photo IDs, when computing facets, then calls repository compute_facets method."""
        # Given
        mock_repo = Mock()
        service = SearchService(repo=mock_repo)
        
        mock_repo.compute_facets.return_value = {
            "date": {"years": []},
            "people": {},
            "tags": {},
            "duplicates": {"exact": 0, "near": 0}
        }
        
        filtered_ids = ["photo1", "photo2", "photo3"]
        
        # When
        facets = service.repo.compute_facets(filtered_ids)
        
        # Then
        mock_repo.compute_facets.assert_called_once_with(filtered_ids)
        
        assert facets["date"] == {"years": []}
        assert facets["people"] == {}
        assert facets["tags"] == {}
        assert facets["duplicates"] == {"exact": 0, "near": 0}


class TestSearchServiceInitialization:
    """Test SearchService initialization and dependency injection."""

    def test_given_repository_when_initializing_service_then_stores_repository(self):
        """Given repository, when initializing service, then stores repository."""
        # Given
        mock_repo = Mock()
        
        # When
        service = SearchService(repo=mock_repo)
        
        # Then
        assert service.repo == mock_repo

    def test_given_service_instance_when_accessing_attributes_then_has_expected_dependencies(self):
        """Given service instance, when accessing attributes, then has expected dependencies."""
        # Given
        mock_repo = Mock()
        
        # When
        service = SearchService(repo=mock_repo)
        
        # Then
        assert hasattr(service, 'repo')
        assert not hasattr(service, 'db')  # Service should not store db directly


class TestSearchServiceIntegration:
    """Test realistic integration scenarios."""

    def test_given_realistic_search_scenario_when_executing_then_coordinates_all_components(self):
        """Given realistic search scenario, when executing, then coordinates all components correctly."""
        # Given
        mock_repo = Mock()
        service = SearchService(repo=mock_repo)
        
        # Mock realistic data
        mock_items = [
            {
                "photo_id": "IMG_001", "path": "/vacation/hawaii/IMG_001.jpg", "ext": "jpg",
                "filesize": 3145728, "shot_ts": "2020-07-15T14:30:00",
                "camera_make": "Apple", "tags": ["vacation"], "people": [], "faces": []
            },
            {
                "photo_id": "IMG_002", "path": "/vacation/hawaii/IMG_002.heic", "ext": "heic",
                "filesize": 2621440, "shot_ts": "2020-07-16T10:15:00",
                "camera_make": "Apple", "tags": ["vacation"], "people": [], "faces": []
            }
        ]
        mock_repo.search_photos.return_value = (mock_items, 25, "next_cursor_abc")
        mock_repo.get_filtered_photo_ids.return_value = ["IMG_001", "IMG_002", "IMG_003", "IMG_004", "IMG_005"]
        
        # Mock facets
        mock_repo.compute_facets.return_value = {
            "date": {
                "years": [{"year": 2020, "count": 25, "months": [{"month": 7, "count": 25}]}]
            },
            "tags": {"vacation": 25, "beach": 12, "mountain": 8, "sunset": 5, "hiking": 3},
            "people": {"person_john": 15, "person_jane": 10},
            "duplicates": {"exact": 2, "near": 1}
        }
        
        request = SearchRequest(
            q="vacation 2020",
            filters=SearchFilters(
                date=DateFilter(from_="2020-01-01", to="2020-12-31"),
                camera_make=["Apple"],
                tags=["vacation"]
            ),
            sort=SortSpec(by="shot_ts", dir="desc"),
            page=PageSpec(limit=50)
        )
        
        # When
        response = service.execute(request)
        
        # Then
        assert response.hits.total == 25
        assert len(response.hits.items) == 2
        assert response.hits.cursor == "next_cursor_abc"
        assert response.facets["tags"]["vacation"] == 25
        assert response.facets["people"]["person_john"] == 15
        
        # Verify all repository interactions
        mock_repo.search_photos.assert_called_once_with(
            filters=request.filters,
            sort=request.sort,
            page=request.page,
            text_query="vacation 2020"
        )
        mock_repo.get_filtered_photo_ids.assert_called_once_with(
            request.filters, "vacation 2020"
        )
        mock_repo.compute_facets.assert_called_once_with(
            ["IMG_001", "IMG_002", "IMG_003", "IMG_004", "IMG_005"]
        )

    def test_given_service_with_different_sort_options_when_executing_then_passes_sort_to_repository(self):
        """Given service with different sort options, when executing, then passes sort to repository."""
        # Given
        mock_repo = Mock()
        service = SearchService(repo=mock_repo)
        
        mock_repo.search_photos.return_value = ([], 0, None)
        mock_repo.get_filtered_photo_ids.return_value = []
        mock_repo.compute_facets.return_value = {}
        
        test_cases = [
            SortSpec(by="shot_ts", dir="asc"),
            SortSpec(by="shot_ts", dir="desc"),
            SortSpec(by="relevance", dir="desc")
        ]
        
        for sort_spec in test_cases:
            # When
            request = SearchRequest(
                filters=SearchFilters(),
                sort=sort_spec,
                page=PageSpec(limit=50)
            )
            service.execute(request)
            
            # Then
            mock_repo.search_photos.assert_called_with(
                filters=request.filters,
                sort=sort_spec,
                page=request.page,
                text_query=None
            )

    def test_given_service_with_pagination_options_when_executing_then_passes_pagination_to_repository(self):
        """Given service with pagination options, when executing, then passes pagination to repository."""
        # Given
        mock_repo = Mock()
        service = SearchService(repo=mock_repo)
        
        mock_repo.search_photos.return_value = ([], 0, None)
        mock_repo.get_filtered_photo_ids.return_value = []
        mock_repo.compute_facets.return_value = {}
        
        test_cases = [
            PageSpec(limit=10),
            PageSpec(limit=50, cursor="cursor123"),
            PageSpec(limit=100, cursor="another_cursor")
        ]
        
        for page_spec in test_cases:
            # When
            request = SearchRequest(
                filters=SearchFilters(),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=page_spec
            )
            service.execute(request)
            
            # Then
            mock_repo.search_photos.assert_called_with(
                filters=request.filters,
                sort=request.sort,
                page=page_spec,
                text_query=None
            )


class TestPhotosRepositorySoftDeleteFiltering:
    def test_search_repository_excludes_soft_deleted_photos_by_default(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-soft-delete.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 24, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "active-photo",
                        "path": "photos/active-photo.jpg",
                        "sha256": "a" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                    {
                        "photo_id": "deleted-photo",
                        "path": "photos/deleted-photo.jpg",
                        "sha256": "b" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": now,
                        "deleted_ts": now,
                        "faces_count": 0,
                        "faces_detected_ts": None,
                    },
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, cursor = repo.search_photos(
                filters=SearchFilters(),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
            )

        assert [item["photo_id"] for item in items] == ["active-photo"]
        assert total == 1
        assert cursor is not None

    def test_get_filtered_photo_ids_excludes_soft_deleted_photos(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-filtered-ids.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 24, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "active-photo",
                        "path": "photos/active-photo.jpg",
                        "sha256": "c" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                    {
                        "photo_id": "deleted-photo",
                        "path": "photos/deleted-photo.jpg",
                        "sha256": "d" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": now,
                        "deleted_ts": now,
                        "faces_count": 0,
                        "faces_detected_ts": None,
                    },
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            photo_ids = repo.get_filtered_photo_ids(SearchFilters())

        assert photo_ids == ["active-photo"]

    def test_date_filter_from_only_includes_start_of_day_matches(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-date-filter-from-only.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        start_of_day = datetime(2022, 7, 1, 0, 0, 0, tzinfo=UTC)
        previous_day = datetime(2022, 6, 30, 23, 59, 59, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "from-match",
                        "path": "photos/from-match.jpg",
                        "sha256": "1" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": start_of_day,
                        "modified_ts": start_of_day,
                        "shot_ts": start_of_day,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": start_of_day,
                        "deleted_ts": None,
                        "faces_count": 0,
                        "faces_detected_ts": None,
                    },
                    {
                        "photo_id": "from-excluded",
                        "path": "photos/from-excluded.jpg",
                        "sha256": "2" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": previous_day,
                        "modified_ts": previous_day,
                        "shot_ts": previous_day,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": previous_day,
                        "deleted_ts": None,
                        "faces_count": 0,
                        "faces_detected_ts": None,
                    },
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(date=DateFilter(from_="2022-07-01")),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
            )

        assert [item["photo_id"] for item in items] == ["from-match"]
        assert total == 1

    def test_date_filter_to_only_includes_end_of_day_fractional_second_matches(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-date-filter-to-only.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        end_of_day_fraction = datetime(2022, 7, 31, 23, 59, 59, 500000, tzinfo=UTC)
        next_day = datetime(2022, 8, 1, 0, 0, 0, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "to-match",
                        "path": "photos/to-match.jpg",
                        "sha256": "3" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": end_of_day_fraction,
                        "modified_ts": end_of_day_fraction,
                        "shot_ts": end_of_day_fraction,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": end_of_day_fraction,
                        "deleted_ts": None,
                        "faces_count": 0,
                        "faces_detected_ts": None,
                    },
                    {
                        "photo_id": "to-excluded",
                        "path": "photos/to-excluded.jpg",
                        "sha256": "4" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": next_day,
                        "modified_ts": next_day,
                        "shot_ts": next_day,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": next_day,
                        "deleted_ts": None,
                        "faces_count": 0,
                        "faces_detected_ts": None,
                    },
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(date=DateFilter(to="2022-07-31")),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
            )

        assert [item["photo_id"] for item in items] == ["to-match"]
        assert total == 1

    def test_date_filter_bounded_includes_full_end_day_and_excludes_null_timestamps(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-date-filter-bounded.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        match_ts = datetime(2022, 7, 31, 23, 59, 59, 999999, tzinfo=UTC)
        outside_ts = datetime(2022, 8, 1, 0, 0, 0, tzinfo=UTC)
        earlier_ts = datetime(2022, 6, 30, 23, 59, 59, tzinfo=UTC)
        now = datetime(2026, 3, 30, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "bounded-match",
                        "path": "photos/bounded-match.jpg",
                        "sha256": "5" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": match_ts,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                    {
                        "photo_id": "bounded-outside",
                        "path": "photos/bounded-outside.jpg",
                        "sha256": "6" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": outside_ts,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                    {
                        "photo_id": "bounded-earlier",
                        "path": "photos/bounded-earlier.jpg",
                        "sha256": "7" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": earlier_ts,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                    {
                        "photo_id": "bounded-null",
                        "path": "photos/bounded-null.jpg",
                        "sha256": "8" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": None,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(date=DateFilter(from_="2022-07-01", to="2022-07-31")),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
            )

        assert [item["photo_id"] for item in items] == ["bounded-match"]
        assert total == 1

    def test_search_repository_filters_by_path_hints(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-path-hints.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 30, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "lake-photo",
                        "path": "seed-corpus/family-events/lake-weekend/lake_weekend_001.jpg",
                        "sha256": "e" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                    {
                        "photo_id": "travel-photo",
                        "path": "seed-corpus/travel/city-break/city_break_001.jpg",
                        "sha256": "f" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(path_hints=["lake-weekend"]),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
            )

        assert [item["photo_id"] for item in items] == ["lake-photo"]
        assert total == 1

    def test_search_repository_combines_path_hints_with_has_faces_false(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-path-hints-no-faces.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 30, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "birthday-no-faces",
                        "path": "seed-corpus/family-events/birthday-park/birthday_park_004.png",
                        "sha256": "1" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "png",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                    {
                        "photo_id": "birthday-with-face",
                        "path": "seed-corpus/family-events/birthday-park/birthday_park_001.jpg",
                        "sha256": "2" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": now,
                        "deleted_ts": None,
                        "faces_count": 1,
                        "faces_detected_ts": now,
                    },
                ],
            )
            connection.execute(
                insert(faces).values(
                    face_id="face-birthday-with-face",
                    photo_id="birthday-with-face",
                    person_id=None,
                    bbox_x=0,
                    bbox_y=0,
                    bbox_w=10,
                    bbox_h=10,
                    bitmap=None,
                    embedding=None,
                    detector_name="seed",
                    detector_version="1",
                    provenance=None,
                    created_ts=now,
                )
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(path_hints=["birthday-park"], has_faces=False),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
            )

        assert [item["photo_id"] for item in items] == ["birthday-no-faces"]
        assert total == 1

    def test_search_repository_filters_by_person_names(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-person-names.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 4, 3, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "photo-inez",
                        "path": "seed-corpus/family/inez_001.jpg",
                        "sha256": "a" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": now,
                        "deleted_ts": None,
                        "faces_count": 1,
                        "faces_detected_ts": now,
                    },
                    {
                        "photo_id": "photo-mateo",
                        "path": "seed-corpus/family/mateo_001.jpg",
                        "sha256": "b" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": now,
                        "deleted_ts": None,
                        "faces_count": 1,
                        "faces_detected_ts": now,
                    },
                ],
            )
            connection.execute(
                insert(people),
                [
                    {
                        "person_id": "person-inez",
                        "display_name": "Inez Rivera",
                        "created_ts": now,
                        "updated_ts": now,
                    },
                    {
                        "person_id": "person-mateo",
                        "display_name": "Mateo Rivera",
                        "created_ts": now,
                        "updated_ts": now,
                    },
                ],
            )
            connection.execute(
                insert(faces),
                [
                    {
                        "face_id": "face-inez",
                        "photo_id": "photo-inez",
                        "person_id": "person-inez",
                        "bbox_x": 0,
                        "bbox_y": 0,
                        "bbox_w": 10,
                        "bbox_h": 10,
                        "bitmap": None,
                        "embedding": None,
                        "detector_name": "seed",
                        "detector_version": "1",
                        "provenance": None,
                        "created_ts": now,
                    },
                    {
                        "face_id": "face-mateo",
                        "photo_id": "photo-mateo",
                        "person_id": "person-mateo",
                        "bbox_x": 0,
                        "bbox_y": 0,
                        "bbox_w": 10,
                        "bbox_h": 10,
                        "bitmap": None,
                        "embedding": None,
                        "detector_name": "seed",
                        "detector_version": "1",
                        "provenance": None,
                        "created_ts": now,
                    },
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(person_names=["inez"]),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
            )

        assert [item["photo_id"] for item in items] == ["photo-inez"]
        assert total == 1

    def test_search_repository_person_names_use_or_semantics(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-person-names-or.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 4, 3, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "photo-inez",
                        "path": "seed-corpus/family/inez_001.jpg",
                        "sha256": "c" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": now,
                        "deleted_ts": None,
                        "faces_count": 1,
                        "faces_detected_ts": now,
                    },
                    {
                        "photo_id": "photo-grandma",
                        "path": "seed-corpus/family/grandma_001.jpg",
                        "sha256": "d" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": now,
                        "deleted_ts": None,
                        "faces_count": 1,
                        "faces_detected_ts": now,
                    },
                    {
                        "photo_id": "photo-jordan",
                        "path": "seed-corpus/family/jordan_001.jpg",
                        "sha256": "e" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": now,
                        "deleted_ts": None,
                        "faces_count": 1,
                        "faces_detected_ts": now,
                    },
                ],
            )
            connection.execute(
                insert(people),
                [
                    {
                        "person_id": "person-inez",
                        "display_name": "Inez Rivera",
                        "created_ts": now,
                        "updated_ts": now,
                    },
                    {
                        "person_id": "person-grandma",
                        "display_name": "Grandma Elena",
                        "created_ts": now,
                        "updated_ts": now,
                    },
                    {
                        "person_id": "person-jordan",
                        "display_name": "Jordan Lee",
                        "created_ts": now,
                        "updated_ts": now,
                    },
                ],
            )
            connection.execute(
                insert(faces),
                [
                    {
                        "face_id": "face-inez",
                        "photo_id": "photo-inez",
                        "person_id": "person-inez",
                        "bbox_x": 0,
                        "bbox_y": 0,
                        "bbox_w": 10,
                        "bbox_h": 10,
                        "bitmap": None,
                        "embedding": None,
                        "detector_name": "seed",
                        "detector_version": "1",
                        "provenance": None,
                        "created_ts": now,
                    },
                    {
                        "face_id": "face-grandma",
                        "photo_id": "photo-grandma",
                        "person_id": "person-grandma",
                        "bbox_x": 0,
                        "bbox_y": 0,
                        "bbox_w": 10,
                        "bbox_h": 10,
                        "bitmap": None,
                        "embedding": None,
                        "detector_name": "seed",
                        "detector_version": "1",
                        "provenance": None,
                        "created_ts": now,
                    },
                    {
                        "face_id": "face-jordan",
                        "photo_id": "photo-jordan",
                        "person_id": "person-jordan",
                        "bbox_x": 0,
                        "bbox_y": 0,
                        "bbox_w": 10,
                        "bbox_h": 10,
                        "bitmap": None,
                        "embedding": None,
                        "detector_name": "seed",
                        "detector_version": "1",
                        "provenance": None,
                        "created_ts": now,
                    },
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(person_names=["inez", "grandma"]),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
            )

        assert {item["photo_id"] for item in items} == {"photo-inez", "photo-grandma"}
        assert "photo-jordan" not in {item["photo_id"] for item in items}
        assert total == 2

    def test_search_repository_person_names_ignore_unlabeled_faces(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-person-names-unlabeled.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 4, 3, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "photo-unlabeled",
                        "path": "seed-corpus/family/unlabeled_001.jpg",
                        "sha256": "e" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": now,
                        "deleted_ts": None,
                        "faces_count": 1,
                        "faces_detected_ts": now,
                    }
                ],
            )
            connection.execute(
                insert(faces).values(
                    face_id="face-unlabeled",
                    photo_id="photo-unlabeled",
                    person_id=None,
                    bbox_x=0,
                    bbox_y=0,
                    bbox_w=10,
                    bbox_h=10,
                    bitmap=None,
                    embedding=None,
                    detector_name="seed",
                    detector_version="1",
                    provenance=None,
                    created_ts=now,
                )
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(person_names=["inez"]),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
            )

        assert items == []
        assert total == 0

    def test_search_repository_requires_all_text_query_tokens(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-text-query-all-tokens.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 30, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "lake-weekend",
                        "path": "seed-corpus/family-events/lake-weekend/lake_weekend_001.jpg",
                        "sha256": "7" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                    {
                        "photo_id": "lake-only",
                        "path": "seed-corpus/family-events/lake-house/lake_house_001.jpg",
                        "sha256": "8" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
                text_query="lake weekend",
            )

        assert [item["photo_id"] for item in items] == ["lake-weekend"]
        assert total == 1

    def test_search_repository_matches_text_query_tokens_across_path_and_tags(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-text-query-path-and-tags.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 30, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "lake-tagged-sunset",
                        "path": "seed-corpus/family-events/lake-weekend/lake_weekend_001.jpg",
                        "sha256": "9" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                    {
                        "photo_id": "lake-tagged-hike",
                        "path": "seed-corpus/family-events/lake-weekend/lake_weekend_002.jpg",
                        "sha256": "a" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                ],
            )
            connection.execute(
                insert(photo_tags),
                [
                    {"photo_id": "lake-tagged-sunset", "tag": "sunset"},
                    {"photo_id": "lake-tagged-hike", "tag": "hike"},
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
                text_query="LAKE sunset",
            )

        assert [item["photo_id"] for item in items] == ["lake-tagged-sunset"]
        assert total == 1

    def test_search_repository_ignores_whitespace_only_text_query(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-text-query-whitespace-only.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 30, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "first-photo",
                        "path": "seed-corpus/family-events/lake-weekend/lake_weekend_001.jpg",
                        "sha256": "b" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                    {
                        "photo_id": "second-photo",
                        "path": "seed-corpus/travel/city-break/city_break_001.jpg",
                        "sha256": "c" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                ],
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            items, total, _ = repo.search_photos(
                filters=SearchFilters(),
                sort=SortSpec(by="shot_ts", dir="desc"),
                page=PageSpec(limit=50),
                text_query="   \t  ",
            )

        assert {item["photo_id"] for item in items} == {"first-photo", "second-photo"}
        assert total == 2


class TestPhotosRepositoryOfflineBrowseIntegration:
    def test_search_repository_exposes_thumbnail_and_original_availability(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-thumbnail-availability.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 28, tzinfo=UTC)
        thumbnail_bytes = b"thumbnail-bytes"

        with engine.begin() as connection:
            connection.execute(
                insert(storage_sources).values(
                    storage_source_id="source-1",
                    display_name="Family NAS",
                    marker_filename=".photo-org-source.json",
                    marker_version=1,
                    availability_state="unreachable",
                    last_failure_reason="permission_denied",
                    last_validated_ts=now,
                    created_ts=now,
                    updated_ts=now,
                )
            )
            connection.execute(
                insert(watched_folders).values(
                    watched_folder_id="watched-folder-1",
                    scan_path="/photos/seed-corpus",
                    storage_source_id="source-1",
                    relative_path=".",
                    display_name="Family NAS / seed-corpus",
                    is_enabled=1,
                    availability_state="unreachable",
                    last_failure_reason="permission_denied",
                    last_successful_scan_ts=now,
                    created_ts=now,
                    updated_ts=now,
                )
            )
            connection.execute(
                insert(photos).values(
                    photo_id="photo-1",
                    path="/photos/seed-corpus/family-events/birthday-park/birthday_park_001.jpg",
                    sha256="e" * 64,
                    phash=None,
                    filesize=100,
                    ext="jpg",
                    created_ts=now,
                    modified_ts=now,
                    shot_ts=now,
                    shot_ts_source=None,
                    camera_make="Apple",
                    camera_model=None,
                    software=None,
                    orientation=None,
                    gps_latitude=None,
                    gps_longitude=None,
                    gps_altitude=None,
                    thumbnail_jpeg=thumbnail_bytes,
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=64,
                    thumbnail_height=48,
                    updated_ts=now,
                    deleted_ts=None,
                    faces_count=0,
                    faces_detected_ts=None,
                )
            )
            connection.execute(
                insert(photo_files).values(
                    photo_file_id="photo-file-1",
                    photo_id="photo-1",
                    watched_folder_id="watched-folder-1",
                    relative_path="family-events/birthday-park/birthday_park_001.jpg",
                    filename="birthday_park_001.jpg",
                    extension="jpg",
                    filesize=100,
                    created_ts=now,
                    modified_ts=now,
                    first_seen_ts=now,
                    last_seen_ts=now,
                    missing_ts=None,
                    deleted_ts=None,
                    lifecycle_state="active",
                    absence_reason=None,
                )
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            service = SearchService(repo=repo)
            response = service.execute(
                SearchRequest(
                    filters=SearchFilters(),
                    sort=SortSpec(by="shot_ts", dir="desc"),
                    page=PageSpec(limit=50),
                )
            )

        assert response.hits.total == 1
        hit = response.hits.items[0]
        assert hit.thumbnail is not None
        assert hit.thumbnail.mime_type == "image/jpeg"
        assert hit.thumbnail.width == 64
        assert hit.thumbnail.height == 48
        assert hit.thumbnail.data_base64 == base64.b64encode(thumbnail_bytes).decode("ascii")
        assert hit.original is not None
        assert hit.original.is_available is False
        assert hit.original.availability_state == "unreachable"
        assert hit.original.last_failure_reason == "permission_denied"


class TestPhotosRepositoryHasFacesFacet:
    def test_compute_facets_includes_has_faces_facet_breakdown(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-has-faces-facet.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 30, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(photos),
                [
                    {
                        "photo_id": "face-photo",
                        "path": "seed-corpus/family-events/lake-weekend/lake_weekend_003.png",
                        "sha256": "3" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "png",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
                        "camera_model": None,
                        "software": None,
                        "orientation": None,
                        "gps_latitude": None,
                        "gps_longitude": None,
                        "gps_altitude": None,
                        "updated_ts": now,
                        "deleted_ts": None,
                        "faces_count": 1,
                        "faces_detected_ts": now,
                    },
                    {
                        "photo_id": "no-face-photo",
                        "path": "seed-corpus/family-events/lake-weekend/lake_weekend_001.jpg",
                        "sha256": "4" * 64,
                        "phash": None,
                        "filesize": 100,
                        "ext": "jpg",
                        "created_ts": now,
                        "modified_ts": now,
                        "shot_ts": now,
                        "shot_ts_source": None,
                        "camera_make": None,
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
                    },
                ],
            )
            connection.execute(
                insert(faces).values(
                    face_id="face-photo-face",
                    photo_id="face-photo",
                    person_id=None,
                    bbox_x=0,
                    bbox_y=0,
                    bbox_w=10,
                    bbox_h=10,
                    bitmap=None,
                    embedding=None,
                    detector_name="seed",
                    detector_version="1",
                    provenance=None,
                    created_ts=now,
                )
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            facets = repo.compute_facets(["face-photo", "no-face-photo"])

        assert facets["has_faces"] == {"true": 1, "false": 1}


class TestSeedCorpusSearchFixtureCatalog:
    def test_fixture_catalog_references_known_manifest_assets(self):
        manifest_asset_ids = {
            asset["asset_id"]
            for asset in _load_seed_manifest()["assets"]
        }

        fixtures = _load_search_fixtures()

        assert fixtures
        for fixture in fixtures:
            assert fixture["scenario_id"]
            assert fixture["description"]
            assert fixture["phase_scope"] == "phase_3"
            SearchRequest.model_validate(fixture["request"])
            assert fixture["expected_asset_ids"]
            assert set(fixture["expected_asset_ids"]).issubset(manifest_asset_ids)


class TestSeedCorpusSearchFixtureExecution:
    @pytest.mark.parametrize(
        "fixture",
        _fixture_scenarios_for_parametrize(),
        ids=lambda fixture: fixture["scenario_id"],
    )
    def test_search_fixture_execution_matches_expected_asset_ids(self, tmp_path, fixture):
        database_url = f"sqlite:///{tmp_path / 'search-fixtures.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)

        with engine.begin() as connection:
            _seed_search_fixture_catalog(connection)

        request = SearchRequest.model_validate(fixture["request"])
        expected_asset_ids = fixture["expected_asset_ids"]
        asset_by_path = _asset_id_by_manifest_path()

        with Session(engine) as session:
            repo = PhotosRepository(session)
            service = SearchService(repo=repo)
            response = service.execute(request)

        returned_asset_ids = [asset_by_path[item.path] for item in response.hits.items]

        assert set(returned_asset_ids) == set(expected_asset_ids)
        assert response.hits.total == len(expected_asset_ids)

    def test_search_repository_excludes_missing_file_rows_from_original_availability(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-missing-original-availability.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 28, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(storage_sources).values(
                    storage_source_id="source-1",
                    display_name="Family NAS",
                    marker_filename=".photo-org-source.json",
                    marker_version=1,
                    availability_state="active",
                    last_failure_reason=None,
                    last_validated_ts=now,
                    created_ts=now,
                    updated_ts=now,
                )
            )
            connection.execute(
                insert(watched_folders).values(
                    watched_folder_id="watched-folder-1",
                    scan_path="/photos/seed-corpus",
                    storage_source_id="source-1",
                    relative_path=".",
                    display_name="Family NAS / seed-corpus",
                    is_enabled=1,
                    availability_state="active",
                    last_failure_reason=None,
                    last_successful_scan_ts=now,
                    created_ts=now,
                    updated_ts=now,
                )
            )
            connection.execute(
                insert(photos).values(
                    photo_id="photo-1",
                    path="/photos/seed-corpus/family-events/birthday-park/birthday_park_001.jpg",
                    sha256="e" * 64,
                    phash=None,
                    filesize=100,
                    ext="jpg",
                    created_ts=now,
                    modified_ts=now,
                    shot_ts=now,
                    shot_ts_source=None,
                    camera_make="Apple",
                    camera_model=None,
                    software=None,
                    orientation=None,
                    gps_latitude=None,
                    gps_longitude=None,
                    gps_altitude=None,
                    thumbnail_jpeg=b"thumbnail-bytes",
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=64,
                    thumbnail_height=48,
                    updated_ts=now,
                    deleted_ts=None,
                    faces_count=0,
                    faces_detected_ts=None,
                )
            )
            connection.execute(
                insert(photo_files).values(
                    photo_file_id="photo-file-1",
                    photo_id="photo-1",
                    watched_folder_id="watched-folder-1",
                    relative_path="family-events/birthday-park/birthday_park_001.jpg",
                    filename="birthday_park_001.jpg",
                    extension="jpg",
                    filesize=100,
                    created_ts=now,
                    modified_ts=now,
                    first_seen_ts=now,
                    last_seen_ts=now,
                    missing_ts=now,
                    deleted_ts=None,
                    lifecycle_state="missing",
                    absence_reason="path_removed",
                )
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            service = SearchService(repo=repo)
            response = service.execute(
                SearchRequest(
                    filters=SearchFilters(),
                    sort=SortSpec(by="shot_ts", dir="desc"),
                    page=PageSpec(limit=50),
                )
            )

        assert response.hits.total == 1
        hit = response.hits.items[0]
        assert hit.original is None

    def test_search_repository_prefers_watched_folder_health_over_storage_source_state(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'search-watched-folder-availability-precedence.db'}"
        upgrade_database(database_url)
        engine = create_engine(database_url, future=True)
        now = datetime(2026, 3, 28, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                insert(storage_sources).values(
                    storage_source_id="source-1",
                    display_name="Family NAS",
                    marker_filename=".photo-org-source.json",
                    marker_version=1,
                    availability_state="active",
                    last_failure_reason=None,
                    last_validated_ts=now,
                    created_ts=now,
                    updated_ts=now,
                )
            )
            connection.execute(
                insert(watched_folders).values(
                    [
                        {
                            "watched_folder_id": "watched-folder-healthy",
                            "scan_path": "/photos/healthy",
                            "storage_source_id": "source-1",
                            "relative_path": "healthy",
                            "display_name": "Healthy Folder",
                            "is_enabled": 1,
                            "availability_state": "active",
                            "last_failure_reason": None,
                            "last_successful_scan_ts": now,
                            "created_ts": now,
                            "updated_ts": now,
                        },
                        {
                            "watched_folder_id": "watched-folder-unreachable",
                            "scan_path": "/photos/offline",
                            "storage_source_id": "source-1",
                            "relative_path": "offline",
                            "display_name": "Offline Folder",
                            "is_enabled": 1,
                            "availability_state": "unreachable",
                            "last_failure_reason": "permission_denied",
                            "last_successful_scan_ts": now,
                            "created_ts": now,
                            "updated_ts": now,
                        },
                    ]
                )
            )
            connection.execute(
                insert(photos).values(
                    photo_id="photo-1",
                    path="/photos/offline/family-events/birthday-park/birthday_park_001.jpg",
                    sha256="f" * 64,
                    phash=None,
                    filesize=100,
                    ext="jpg",
                    created_ts=now,
                    modified_ts=now,
                    shot_ts=now,
                    shot_ts_source=None,
                    camera_make="Apple",
                    camera_model=None,
                    software=None,
                    orientation=None,
                    gps_latitude=None,
                    gps_longitude=None,
                    gps_altitude=None,
                    thumbnail_jpeg=b"thumbnail-bytes",
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=64,
                    thumbnail_height=48,
                    updated_ts=now,
                    deleted_ts=None,
                    faces_count=0,
                    faces_detected_ts=None,
                )
            )
            connection.execute(
                insert(photo_files).values(
                    photo_file_id="photo-file-1",
                    photo_id="photo-1",
                    watched_folder_id="watched-folder-unreachable",
                    relative_path="family-events/birthday-park/birthday_park_001.jpg",
                    filename="birthday_park_001.jpg",
                    extension="jpg",
                    filesize=100,
                    created_ts=now,
                    modified_ts=now,
                    first_seen_ts=now,
                    last_seen_ts=now,
                    missing_ts=None,
                    deleted_ts=None,
                    lifecycle_state="active",
                    absence_reason=None,
                )
            )

        with Session(engine) as session:
            repo = PhotosRepository(session)
            service = SearchService(repo=repo)
            response = service.execute(
                SearchRequest(
                    filters=SearchFilters(),
                    sort=SortSpec(by="shot_ts", dir="desc"),
                    page=PageSpec(limit=50),
                )
            )

        assert response.hits.total == 1
        hit = response.hits.items[0]
        assert hit.original is not None
        assert hit.original.is_available is False
        assert hit.original.availability_state == "unreachable"
        assert hit.original.last_failure_reason == "permission_denied"
