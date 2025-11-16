"""
Unit tests for the new domain-based facet architecture.

These tests demonstrate the benefits of treating facets as first-class domain entities.
"""

import pytest
from unittest.mock import Mock, MagicMock
from app.domain.facets import (
    TagsFacet, PeopleFacet, DateHierarchyFacet, DuplicatesFacet,
    FacetContext, FacetRegistry, FacetType, FacetValue, FacetResult
)


class TestTagsFacet:
    """Test the TagsFacet domain entity."""
    
    def test_given_tags_facet_when_computing_then_returns_facet_result(self):
        """Given a TagsFacet, when computing, then returns proper FacetResult."""
        # Given
        facet = TagsFacet()
        mock_db = Mock()
        mock_photo_tags = Mock()
        
        # Mock the table columns
        mock_photo_tags.c = {
            'tag': Mock(),
            'photo_id': Mock()
        }
        
        # Mock query result
        mock_db.execute.return_value.all.return_value = [
            ('vacation', 5),
            ('beach', 3),
            ('sunset', 2)
        ]
        
        context = FacetContext(
            db=mock_db,
            photo_tags=mock_photo_tags,
            faces=Mock(),
            photos=Mock()
        )
        
        # When
        result = facet.compute(['photo1', 'photo2'], context)
        
        # Then
        assert isinstance(result, FacetResult)
        assert result.facet_name == "tags"
        assert result.facet_type == FacetType.SIMPLE_COUNT
        assert len(result.values) == 3
        
        # Check values are sorted by count descending
        assert result.values[0].value == "vacation"
        assert result.values[0].count == 5
        assert result.values[1].value == "beach"
        assert result.values[1].count == 3
        assert result.values[2].value == "sunset"
        assert result.values[2].count == 2
        
        # Check total count
        assert result.total_count == 10  # 5 + 3 + 2
    
    def test_given_tags_facet_when_checking_drill_sideways_then_returns_true(self):
        """Given a TagsFacet, when checking drill sideways support, then returns True."""
        # Given
        facet = TagsFacet()
        
        # When/Then
        assert facet.supports_drill_sideways() == True
    
    def test_given_tags_facet_when_generating_cache_key_then_includes_name_and_ids(self):
        """Given a TagsFacet, when generating cache key, then includes facet name and photo IDs."""
        # Given
        facet = TagsFacet()
        photo_ids = ['photo1', 'photo2', 'photo3']
        
        # When
        cache_key = facet.get_cache_key(photo_ids)
        
        # Then
        assert cache_key.startswith("tags:")
        assert isinstance(cache_key, str)
    
    def test_given_tags_facet_when_computing_with_null_values_then_filters_nulls(self):
        """Given a TagsFacet, when computing with null values, then filters out nulls."""
        # Given
        facet = TagsFacet()
        mock_db = Mock()
        mock_photo_tags = Mock()
        
        # Mock the table columns
        mock_photo_tags.c = {
            'tag': Mock(),
            'photo_id': Mock()
        }
        
        # Mock query result with null values
        mock_db.execute.return_value.all.return_value = [
            ('vacation', 5),
            (None, 2),  # Should be filtered out
            ('beach', 3),
        ]
        
        context = FacetContext(
            db=mock_db,
            photo_tags=mock_photo_tags,
            faces=Mock(),
            photos=Mock()
        )
        
        # When
        result = facet.compute(['photo1', 'photo2'], context)
        
        # Then
        assert len(result.values) == 2  # Null value filtered out
        assert all(v.value is not None for v in result.values)


class TestFacetRegistry:
    """Test the FacetRegistry coordination."""
    
    def test_given_registry_when_initialized_then_has_default_facets(self):
        """Given a FacetRegistry, when initialized, then has default facets registered."""
        # Given/When
        registry = FacetRegistry()
        
        # Then
        assert registry.get_facet("tags") is not None
        assert registry.get_facet("people") is not None
        assert registry.get_facet("date") is not None
        assert registry.get_facet("duplicates") is not None
        
        assert isinstance(registry.get_facet("tags"), TagsFacet)
        assert isinstance(registry.get_facet("people"), PeopleFacet)
        assert isinstance(registry.get_facet("date"), DateHierarchyFacet)
        assert isinstance(registry.get_facet("duplicates"), DuplicatesFacet)
    
    def test_given_registry_when_registering_custom_facet_then_can_retrieve_it(self):
        """Given a FacetRegistry, when registering custom facet, then can retrieve it."""
        # Given
        registry = FacetRegistry()
        
        class CustomFacet(TagsFacet):
            def __init__(self):
                super().__init__()
                self.name = "custom"
        
        custom_facet = CustomFacet()
        
        # When
        registry.register(custom_facet)
        
        # Then
        retrieved = registry.get_facet("custom")
        assert retrieved is custom_facet
        assert retrieved.name == "custom"
    
    def test_given_registry_when_getting_nonexistent_facet_then_returns_none(self):
        """Given a FacetRegistry, when getting nonexistent facet, then returns None."""
        # Given
        registry = FacetRegistry()
        
        # When/Then
        assert registry.get_facet("nonexistent") is None
    
    def test_given_registry_when_getting_all_facets_then_returns_list(self):
        """Given a FacetRegistry, when getting all facets, then returns list of facets."""
        # Given
        registry = FacetRegistry()
        
        # When
        all_facets = registry.get_all_facets()
        
        # Then
        assert isinstance(all_facets, list)
        assert len(all_facets) == 4  # Default facets
        assert all(hasattr(f, 'compute') for f in all_facets)
        assert all(hasattr(f, 'supports_drill_sideways') for f in all_facets)


class TestFacetValue:
    """Test the FacetValue data structure."""
    
    def test_given_facet_value_when_created_then_has_expected_attributes(self):
        """Given a FacetValue, when created, then has expected attributes."""
        # Given/When
        value = FacetValue(value="vacation", count=5)
        
        # Then
        assert value.value == "vacation"
        assert value.count == 5
        assert value.metadata is None
        assert value.children is None
    
    def test_given_facet_value_when_created_with_children_then_supports_hierarchy(self):
        """Given a FacetValue, when created with children, then supports hierarchy."""
        # Given
        child1 = FacetValue(value="january", count=3)
        child2 = FacetValue(value="february", count=2)
        
        # When
        parent = FacetValue(value=2020, count=5, children=[child1, child2])
        
        # Then
        assert parent.value == 2020
        assert parent.count == 5
        assert len(parent.children) == 2
        assert parent.children[0].value == "january"
        assert parent.children[1].value == "february"


class TestFacetResult:
    """Test the FacetResult data structure."""
    
    def test_given_facet_result_when_created_then_has_expected_attributes(self):
        """Given a FacetResult, when created, then has expected attributes."""
        # Given
        values = [
            FacetValue(value="vacation", count=5),
            FacetValue(value="beach", count=3)
        ]
        
        # When
        result = FacetResult(
            facet_name="tags",
            facet_type=FacetType.SIMPLE_COUNT,
            values=values,
            total_count=8
        )
        
        # Then
        assert result.facet_name == "tags"
        assert result.facet_type == FacetType.SIMPLE_COUNT
        assert len(result.values) == 2
        assert result.total_count == 8
        assert result.metadata is None


class TestFacetArchitecturalBenefits:
    """Test the architectural benefits of the new facet system."""
    
    def test_given_facets_when_extending_with_new_facet_then_easy_to_add(self):
        """Given facet system, when extending with new facet, then easy to add."""
        # Given - Create a custom facet
        class CameraModelFacet(TagsFacet):
            def __init__(self):
                super().__init__()
                self.name = "camera_models"
                self.table_name = "photos"
                self.value_column = "camera_model"
        
        registry = FacetRegistry()
        
        # When
        registry.register(CameraModelFacet())
        
        # Then
        camera_facet = registry.get_facet("camera_models")
        assert camera_facet is not None
        assert camera_facet.name == "camera_models"
        assert camera_facet.supports_drill_sideways() == True
    
    def test_given_facets_when_testing_individually_then_isolated_and_focused(self):
        """Given facets, when testing individually, then isolated and focused."""
        # Given
        tags_facet = TagsFacet()
        people_facet = PeopleFacet()
        
        # When/Then - Each facet can be tested in isolation
        assert tags_facet.name == "tags"
        assert tags_facet.table_name == "photo_tags"
        assert tags_facet.value_column == "tag"
        
        assert people_facet.name == "people"
        assert people_facet.table_name == "faces"
        assert people_facet.value_column == "person_id"
        
        # Both support drill sideways
        assert tags_facet.supports_drill_sideways() == True
        assert people_facet.supports_drill_sideways() == True
    
    def test_given_facets_when_comparing_types_then_polymorphic_behavior(self):
        """Given facets, when comparing types, then demonstrates polymorphic behavior."""
        # Given
        tags_facet = TagsFacet()
        date_facet = DateHierarchyFacet()
        duplicates_facet = DuplicatesFacet()
        
        # When/Then - Different facets have different behaviors
        assert tags_facet.facet_type == FacetType.SIMPLE_COUNT
        assert date_facet.facet_type == FacetType.DATE_HIERARCHY
        assert duplicates_facet.facet_type == FacetType.DUPLICATE_STATS
        
        # Different drill-sideways support
        assert tags_facet.supports_drill_sideways() == True
        assert date_facet.supports_drill_sideways() == True
        assert duplicates_facet.supports_drill_sideways() == False