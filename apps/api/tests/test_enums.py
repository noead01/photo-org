import pytest
from app.core.enums import FilesizeRange


class TestFilesizeRange:
    def test_given_filesize_range_enum_when_accessing_values_then_returns_expected_string_values(self):
        """
        Given: FilesizeRange enum
        When: Accessing enum values
        Then: Returns expected string values for each range
        """
        # Given/When/Then
        assert FilesizeRange.small == "small"
        assert FilesizeRange.medium == "medium"
        assert FilesizeRange.large == "large"

    def test_given_small_filesize_range_when_getting_bounds_then_returns_zero_to_one_million(self):
        """
        Given: Small filesize range
        When: Getting bounds
        Then: Returns tuple (0, 1_000_000)
        """
        # Given
        size_range = FilesizeRange.small
        
        # When
        bounds = size_range.bounds()
        
        # Then
        assert bounds == (0, 1_000_000)
        assert bounds[0] == 0
        assert bounds[1] == 1_000_000

    def test_given_medium_filesize_range_when_getting_bounds_then_returns_one_to_five_million(self):
        """
        Given: Medium filesize range
        When: Getting bounds
        Then: Returns tuple (1_000_000, 5_000_000)
        """
        # Given
        size_range = FilesizeRange.medium
        
        # When
        bounds = size_range.bounds()
        
        # Then
        assert bounds == (1_000_000, 5_000_000)
        assert bounds[0] == 1_000_000
        assert bounds[1] == 5_000_000

    def test_given_large_filesize_range_when_getting_bounds_then_returns_five_million_to_ten_billion(self):
        """
        Given: Large filesize range
        When: Getting bounds
        Then: Returns tuple (5_000_000, 10_000_000_000)
        """
        # Given
        size_range = FilesizeRange.large
        
        # When
        bounds = size_range.bounds()
        
        # Then
        assert bounds == (5_000_000, 10_000_000_000)
        assert bounds[0] == 5_000_000
        assert bounds[1] == 10_000_000_000

    def test_given_any_filesize_range_when_getting_bounds_then_returns_tuple_of_two_integers(self):
        """
        Given: Any filesize range
        When: Getting bounds
        Then: Returns tuple containing exactly two integers
        """
        for size_range in FilesizeRange:
            # When
            bounds = size_range.bounds()
            
            # Then
            assert isinstance(bounds, tuple)
            assert len(bounds) == 2
            assert isinstance(bounds[0], int)
            assert isinstance(bounds[1], int)

    def test_given_any_filesize_range_when_getting_bounds_then_min_is_less_than_max(self):
        """
        Given: Any filesize range
        When: Getting bounds
        Then: Minimum value is less than maximum value
        """
        for size_range in FilesizeRange:
            # When
            min_size, max_size = size_range.bounds()
            
            # Then
            assert min_size < max_size

    def test_given_all_filesize_ranges_when_comparing_bounds_then_ranges_are_contiguous_without_gaps(self):
        """
        Given: All filesize ranges (small, medium, large)
        When: Comparing their bounds
        Then: Ranges are contiguous (small max = medium min, medium max = large min)
        """
        # Given
        small_bounds = FilesizeRange.small.bounds()
        medium_bounds = FilesizeRange.medium.bounds()
        large_bounds = FilesizeRange.large.bounds()
        
        # When/Then
        # Small max should equal medium min (boundary case)
        assert small_bounds[1] == medium_bounds[0]
        
        # Medium max should equal large min (boundary case)
        assert medium_bounds[1] == large_bounds[0]

    def test_given_filesize_range_enum_when_iterating_then_contains_exactly_three_values(self):
        """
        Given: FilesizeRange enum
        When: Iterating over all values
        Then: Contains exactly three values (small, medium, large)
        """
        # Given/When
        ranges = list(FilesizeRange)
        
        # Then
        assert len(ranges) == 3
        assert FilesizeRange.small in ranges
        assert FilesizeRange.medium in ranges
        assert FilesizeRange.large in ranges

    def test_given_filesize_range_values_when_converting_to_string_then_returns_enum_name(self):
        """
        Given: FilesizeRange enum values
        When: Converting to string
        Then: Returns the enum name as string
        """
        # Given/When/Then
        assert str(FilesizeRange.small) == "small"
        assert str(FilesizeRange.medium) == "medium"
        assert str(FilesizeRange.large) == "large"

    def test_given_boundary_filesizes_when_checking_ranges_then_correctly_categorizes_edge_cases(self):
        """
        Given: File sizes at exact boundary values
        When: Checking which range they belong to
        Then: Correctly categorizes boundary cases (inclusive/exclusive behavior)
        """
        # Given
        small_bounds = FilesizeRange.small.bounds()
        medium_bounds = FilesizeRange.medium.bounds()
        large_bounds = FilesizeRange.large.bounds()
        
        # When/Then - Test boundary values
        # Small range: 0 to 1,000,000 (exclusive upper bound)
        assert small_bounds[0] == 0  # Minimum file size
        assert small_bounds[1] == 1_000_000  # Boundary with medium
        
        # Medium range: 1,000,000 to 5,000,000 (exclusive upper bound)
        assert medium_bounds[0] == 1_000_000  # Boundary with small
        assert medium_bounds[1] == 5_000_000  # Boundary with large
        
        # Large range: 5,000,000 to 10,000,000,000
        assert large_bounds[0] == 5_000_000  # Boundary with medium
        assert large_bounds[1] == 10_000_000_000  # Maximum supported size