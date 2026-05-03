from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy import Column, DateTime, MetaData, String, Table

from app.domain.facets import (
    DateHierarchyFacet,
    PeopleFacet,
    TagsFacet,
    DuplicatesFacet,
    FacetContext,
    FacetRegistry,
    FacetType,
    FacetValue,
    FacetResult,
)


def _make_photos_table():
    metadata = MetaData()
    return Table(
        "photos",
        metadata,
        Column("photo_id", String),
        Column("shot_ts", DateTime),
        Column("sha256", String),
        Column("phash", String),
    )


def _make_faces_table():
    metadata = MetaData()
    return Table(
        "faces",
        metadata,
        Column("face_id", String),
        Column("photo_id", String),
        Column("person_id", String),
    )


def _make_photo_tags_table():
    metadata = MetaData()
    return Table(
        "photo_tags",
        metadata,
        Column("photo_id", String),
        Column("tag", String),
    )


def _make_face_labels_table():
    metadata = MetaData()
    return Table(
        "face_labels",
        metadata,
        Column("face_id", String),
        Column("person_id", String),
        Column("label_source", String),
    )


def _make_face_suggestions_table():
    metadata = MetaData()
    return Table(
        "face_suggestions",
        metadata,
        Column("face_id", String),
        Column("person_id", String),
        Column("confidence", String),
    )


def _make_context(db, photos=None, faces=None, photo_tags=None, face_labels=None, face_suggestions=None, filters=None):
    return FacetContext(
        db=db,
        photos=photos or _make_photos_table(),
        faces=faces or _make_faces_table(),
        photo_tags=photo_tags or _make_photo_tags_table(),
        face_labels=face_labels or _make_face_labels_table(),
        face_suggestions=face_suggestions or _make_face_suggestions_table(),
        filters=filters,
    )


class TestDateFacetLogic:
    """Test the date aggregation logic in DateHierarchyFacet."""

    def test_given_no_photos_when_computing_then_returns_empty_result(self):
        facet = DateHierarchyFacet()
        mock_db = Mock()
        mock_db.execute.return_value.all.return_value = []

        result = facet.compute(["photo1", "photo2"], _make_context(mock_db))

        assert result.values == []
        assert result.total_count == 0

    def test_given_single_photo_timestamp_then_returns_hierarchy(self):
        facet = DateHierarchyFacet()
        mock_db = Mock()
        test_date = datetime(2023, 6, 15, 10, 30, 45)
        mock_db.execute.return_value.all.return_value = [(test_date,)]

        result = facet.compute(["photo1"], _make_context(mock_db))

        assert len(result.values) == 1
        year_bucket = result.values[0]
        assert year_bucket.value == 2023
        assert year_bucket.count == 1
        year_children = year_bucket.children
        assert year_children is not None
        assert len(year_children) == 1
        month_bucket = year_children[0]
        assert month_bucket.value == 6
        assert month_bucket.count == 1
        month_children = month_bucket.children
        assert month_children is not None
        assert len(month_children) == 1
        day_bucket = month_children[0]
        assert day_bucket.value == 15
        assert day_bucket.count == 1

    def test_date_facet_multiple_years_months_days(self):
        facet = DateHierarchyFacet()
        mock_db = Mock()
        dates = [
            datetime(2022, 12, 31, 10, 0, 0),
            datetime(2023, 1, 1, 12, 0, 0),
            datetime(2023, 6, 15, 16, 0, 0),
            datetime(2023, 6, 16, 16, 0, 0),
        ]
        mock_db.execute.return_value.all.return_value = [(d,) for d in dates]

        result = facet.compute(
            ["photo1", "photo2", "photo3", "photo4"], _make_context(mock_db)
        )

        assert len(result.values) == 2
        year_2022, year_2023 = result.values
        assert year_2022.value == 2022
        assert year_2022.count == 1
        year_2022_children = year_2022.children
        assert year_2022_children is not None
        assert len(year_2022_children) == 1
        assert year_2023.value == 2023
        assert year_2023.count == 3
        year_2023_children = year_2023.children
        assert year_2023_children is not None
        assert len(year_2023_children) == 2

    def test_given_mixed_datetime_and_invalid_values_then_ignores_invalid(self):
        facet = DateHierarchyFacet()
        mock_db = Mock()
        mock_db.execute.return_value.all.return_value = [
            (datetime(2023, 6, 15, 10, 30, 45),),
            ("not_a_date",),
            (datetime(2023, 6, 16, 10, 30, 45),),
        ]

        result = facet.compute(
            ["photo1", "photo2", "photo3", "photo4"], _make_context(mock_db)
        )

        assert result.total_count == 2
        assert result.values
        first_year = result.values[0]
        first_year_children = first_year.children
        assert first_year_children is not None
        first_month = first_year_children[0]
        first_month_children = first_month.children
        assert first_month_children is not None
        assert len(first_month_children) == 2


class TestPeopleFacetLogic:
    """Test the people aggregation logic in PeopleFacet."""

    def test_people_facet_empty_results(self):
        facet = PeopleFacet()
        mock_db = Mock()
        mock_db.execute.return_value.all.return_value = []

        result = facet.compute(["photo1"], _make_context(mock_db))

        assert result.values == []

    def test_people_facet_single_person(self):
        facet = PeopleFacet()
        mock_db = Mock()
        mock_db.execute.return_value.all.return_value = [("person_ines", 2)]

        result = facet.compute(["photo1", "photo2"], _make_context(mock_db))

        assert len(result.values) == 1
        assert result.values[0].value == "person_ines"
        assert result.values[0].count == 2

    def test_people_facet_filters_null_person_ids(self):
        facet = PeopleFacet()
        mock_db = Mock()
        mock_db.execute.return_value.all.return_value = [
            ("person_ines", 2),
            (None, 5),
        ]

        result = facet.compute(["photo1", "photo2"], _make_context(mock_db))

        assert len(result.values) == 1
        assert result.values[0].value == "person_ines"

    def test_people_facet_certainty_mode_human_only(self):
        facet = PeopleFacet()
        mock_db = Mock()
        mock_db.execute.return_value.all.return_value = [("person_ines", 3)]
        filters = SimpleNamespace(person_certainty_mode="human_only", suggestion_confidence_min=None)

        result = facet.compute(["photo1", "photo2", "photo3"], _make_context(mock_db, filters=filters))

        assert len(result.values) == 1
        assert result.values[0].value == "person_ines"
        assert result.values[0].count == 3

    def test_people_facet_certainty_mode_include_suggestions_respects_suggestion_confidence(self):
        facet = PeopleFacet()
        mock_db = Mock()
        mock_db.execute.return_value.all.return_value = [("person_ines", 2), ("person_mateo", 1)]
        filters = SimpleNamespace(person_certainty_mode="include_suggestions", suggestion_confidence_min=0.8)

        result = facet.compute(["photo1", "photo2", "photo3"], _make_context(mock_db, filters=filters))

        assert len(result.values) == 2
        assert result.values[0].value == "person_ines"
        assert result.values[0].count == 2


class TestTagsFacetLogic:
    """Test the tags aggregation logic in TagsFacet."""

    def test_tags_facet_empty_results(self):
        facet = TagsFacet()
        mock_db = Mock()
        mock_db.execute.return_value.all.return_value = []

        result = facet.compute(["photo1"], _make_context(mock_db))

        assert result.values == []

    def test_tags_facet_single_tag(self):
        facet = TagsFacet()
        mock_db = Mock()
        mock_db.execute.return_value.all.return_value = [("beach", 3)]

        result = facet.compute(["photo1", "photo2"], _make_context(mock_db))

        assert len(result.values) == 1
        assert result.values[0].value == "beach"
        assert result.values[0].count == 3

    def test_tags_facet_filters_null_values(self):
        facet = TagsFacet()
        mock_db = Mock()
        mock_db.execute.return_value.all.return_value = [
            ("vacation", 5),
            (None, 2),
        ]

        result = facet.compute(["photo1", "photo2"], _make_context(mock_db))

        assert len(result.values) == 1
        assert result.values[0].value == "vacation"


class TestDuplicatesFacetLogic:
    """Test the duplicates aggregation logic in DuplicatesFacet."""

    def test_duplicates_facet_result_format(self):
        facet = DuplicatesFacet()
        mock_db = Mock()
        mock_db.execute.side_effect = [
            Mock(scalar_one=Mock(return_value=2)),
            Mock(scalar_one=Mock(return_value=5)),
        ]

        result = facet.compute(["photo1", "photo2"], _make_context(mock_db))

        assert result.metadata == {"exact": 2, "near": 5}
        assert result.total_count == 7

    def test_duplicates_facet_handles_empty_filtered_ids(self):
        facet = DuplicatesFacet()
        mock_db = Mock()

        result = facet.compute([], _make_context(mock_db))

        assert result.metadata == {"exact": 0, "near": 0}
        assert result.total_count == 0


class TestTagsFacetDomain:
    """Domain-level tests for TagsFacet behavior."""

    def test_given_tags_facet_when_computing_then_returns_facet_result(self):
        facet = TagsFacet()
        mock_db = Mock()
        photo_tags_table = _make_photo_tags_table()
        mock_db.execute.return_value.all.return_value = [
            ("vacation", 5),
            ("beach", 3),
            ("sunset", 2),
        ]
        context = FacetContext(
            db=mock_db,
            photo_tags=photo_tags_table,
            faces=Mock(),
            photos=Mock(),
        )

        result = facet.compute(["photo1", "photo2"], context)

        assert isinstance(result, FacetResult)
        assert result.facet_name == "tags"
        assert result.facet_type == FacetType.SIMPLE_COUNT
        assert len(result.values) == 3
        assert result.values[0].value == "vacation"
        assert result.values[0].count == 5
        assert result.values[1].value == "beach"
        assert result.values[1].count == 3
        assert result.values[2].value == "sunset"
        assert result.values[2].count == 2
        assert result.total_count == 10

    def test_given_tags_facet_when_checking_drill_sideways_then_returns_true(self):
        facet = TagsFacet()

        assert facet.supports_drill_sideways() is True

    def test_given_tags_facet_when_generating_cache_key_then_includes_name_and_ids(self):
        facet = TagsFacet()
        photo_ids = ["photo1", "photo2", "photo3"]

        cache_key = facet.get_cache_key(photo_ids)

        assert cache_key.startswith("tags:")
        assert isinstance(cache_key, str)

    def test_given_tags_facet_when_computing_with_null_values_then_filters_nulls(self):
        facet = TagsFacet()
        mock_db = Mock()
        photo_tags_table = _make_photo_tags_table()
        mock_db.execute.return_value.all.return_value = [
            ("vacation", 5),
            (None, 2),
            ("beach", 3),
        ]
        context = FacetContext(
            db=mock_db,
            photo_tags=photo_tags_table,
            faces=Mock(),
            photos=Mock(),
        )

        result = facet.compute(["photo1", "photo2"], context)

        assert len(result.values) == 2
        assert all(v.value is not None for v in result.values)


class TestFacetRegistry:
    """Test the FacetRegistry coordination."""

    def test_given_registry_when_initialized_then_has_default_facets(self):
        registry = FacetRegistry()

        assert isinstance(registry.get_facet("tags"), TagsFacet)
        assert isinstance(registry.get_facet("people"), PeopleFacet)
        assert isinstance(registry.get_facet("date"), DateHierarchyFacet)
        assert isinstance(registry.get_facet("duplicates"), DuplicatesFacet)

    def test_given_registry_when_registering_custom_facet_then_can_retrieve_it(self):
        registry = FacetRegistry()

        class CustomFacet(TagsFacet):
            def __init__(self) -> None:
                super().__init__()
                self.name = "custom"

        custom_facet = CustomFacet()
        registry.register(custom_facet)

        retrieved = registry.get_facet("custom")
        assert retrieved is not None
        assert retrieved is custom_facet
        assert retrieved.name == "custom"

    def test_given_registry_when_getting_nonexistent_facet_then_returns_none(self):
        registry = FacetRegistry()

        assert registry.get_facet("nonexistent") is None

    def test_given_registry_when_getting_all_facets_then_returns_list(self):
        registry = FacetRegistry()

        all_facets = registry.get_all_facets()

        assert isinstance(all_facets, list)
        assert len(all_facets) == 4
        assert all(hasattr(f, "compute") for f in all_facets)
        assert all(hasattr(f, "supports_drill_sideways") for f in all_facets)


class TestFacetValue:
    """Test the FacetValue data structure."""

    def test_given_facet_value_when_created_then_has_expected_attributes(self):
        value = FacetValue(value="vacation", count=5)

        assert value.value == "vacation"
        assert value.count == 5
        assert value.metadata is None
        assert value.children is None

    def test_given_facet_value_when_created_with_children_then_supports_hierarchy(self):
        child1 = FacetValue(value="january", count=3)
        child2 = FacetValue(value="february", count=2)

        parent = FacetValue(value=2020, count=5, children=[child1, child2])

        assert parent.value == 2020
        assert parent.count == 5
        parent_children = parent.children
        assert parent_children is not None
        assert len(parent_children) == 2
        assert parent_children[0].value == "january"
        assert parent_children[1].value == "february"


class TestFacetResult:
    """Test the FacetResult data structure."""

    def test_given_facet_result_when_created_then_has_expected_attributes(self):
        values = [
            FacetValue(value="vacation", count=5),
            FacetValue(value="beach", count=3),
        ]

        result = FacetResult(
            facet_name="tags",
            facet_type=FacetType.SIMPLE_COUNT,
            values=values,
            total_count=8,
        )

        assert result.facet_name == "tags"
        assert result.facet_type == FacetType.SIMPLE_COUNT
        assert len(result.values) == 2
        assert result.total_count == 8
        assert result.metadata is None


class TestFacetArchitecturalBenefits:
    """Higher-level architectural tests for the facet system."""

    def test_given_facets_when_extending_with_new_facet_then_easy_to_add(self):
        class CameraModelFacet(TagsFacet):
            def __init__(self) -> None:
                super().__init__()
                self.name = "camera_models"
                self.table_name = "photos"
                self.value_column = "camera_model"

        registry = FacetRegistry()
        registry.register(CameraModelFacet())

        camera_facet = registry.get_facet("camera_models")
        assert camera_facet is not None
        assert camera_facet.name == "camera_models"
        assert camera_facet.supports_drill_sideways() is True

    def test_given_facets_when_testing_individually_then_isolated_and_focused(self):
        tags_facet = TagsFacet()
        people_facet = PeopleFacet()

        assert tags_facet.name == "tags"
        assert tags_facet.table_name == "photo_tags"
        assert tags_facet.value_column == "tag"
        assert people_facet.name == "people"
        assert people_facet.table_name == "faces"
        assert people_facet.value_column == "person_id"
        assert tags_facet.supports_drill_sideways() is True
        assert people_facet.supports_drill_sideways() is True

    def test_given_facets_when_comparing_types_then_polymorphic_behavior(self):
        tags_facet = TagsFacet()
        date_facet = DateHierarchyFacet()
        duplicates_facet = DuplicatesFacet()

        assert tags_facet.facet_type == FacetType.SIMPLE_COUNT
        assert date_facet.facet_type == FacetType.DATE_HIERARCHY
        assert duplicates_facet.facet_type == FacetType.DUPLICATE_STATS
        assert tags_facet.supports_drill_sideways() is True
        assert date_facet.supports_drill_sideways() is True
        assert duplicates_facet.supports_drill_sideways() is False
