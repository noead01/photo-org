"""
Unit tests for SearchService using proper dependency injection.

Tests the business logic orchestration layer that coordinates between
the repository and facet computation services.
"""

import pytest
from unittest.mock import Mock
from datetime import datetime

from app.services.search_service import SearchService
from app.schemas.search_request import SearchRequest, SearchFilters, SortSpec, PageSpec, DateFilter
from app.schemas.search_response import SearchResponse, Hits, PhotoHit
from app.core.enums import FilesizeRange


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