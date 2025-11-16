import pytest
from datetime import datetime, timezone, timedelta
from app.core.pagination import iso_utc, encode_cursor, decode_cursor


class TestIsoUtc:
    def test_given_utc_datetime_when_converting_then_returns_iso_string_with_z_suffix(self):
        """
        Given: A datetime with UTC timezone
        When: Converting to ISO UTC string
        Then: Returns ISO format with 'Z' suffix
        """
        # Given
        dt = datetime(2023, 12, 25, 10, 30, 45, tzinfo=timezone.utc)
        
        # When
        result = iso_utc(dt)
        
        # Then
        assert result == "2023-12-25T10:30:45Z"

    def test_given_naive_datetime_when_converting_then_assumes_utc_and_returns_iso_string(self):
        """
        Given: A naive datetime (no timezone info)
        When: Converting to ISO UTC string
        Then: Assumes UTC timezone and returns ISO format with 'Z' suffix
        """
        # Given
        dt = datetime(2023, 12, 25, 10, 30, 45)
        
        # When
        result = iso_utc(dt)
        
        # Then
        assert result == "2023-12-25T10:30:45Z"

    def test_given_non_utc_timezone_when_converting_then_converts_to_utc_and_returns_iso_string(self):
        """
        Given: A datetime with non-UTC timezone (+5 hours)
        When: Converting to ISO UTC string
        Then: Converts to UTC and returns ISO format with 'Z' suffix
        """
        # Given
        tz_offset = timezone(timedelta(hours=5))
        dt = datetime(2023, 12, 25, 15, 30, 45, tzinfo=tz_offset)
        
        # When
        result = iso_utc(dt)
        
        # Then (15:30 + 5 hours offset = 10:30 UTC)
        assert result == "2023-12-25T10:30:45Z"

    def test_given_datetime_with_microseconds_when_converting_then_preserves_microseconds_in_output(self):
        """
        Given: A datetime with microseconds precision
        When: Converting to ISO UTC string
        Then: Preserves microseconds in the output
        """
        # Given
        dt = datetime(2023, 12, 25, 10, 30, 45, 123456, tzinfo=timezone.utc)
        
        # When
        result = iso_utc(dt)
        
        # Then
        assert result == "2023-12-25T10:30:45.123456Z"

    def test_given_datetime_with_zero_microseconds_when_converting_then_omits_microseconds_from_output(self):
        """
        Given: A datetime with zero microseconds
        When: Converting to ISO UTC string
        Then: Omits microseconds from the output (no trailing .000000)
        """
        # Given
        dt = datetime(2023, 12, 25, 10, 30, 45, 0, tzinfo=timezone.utc)
        
        # When
        result = iso_utc(dt)
        
        # Then
        assert result == "2023-12-25T10:30:45Z"

    def test_given_datetime_at_year_boundary_when_converting_then_handles_edge_case_correctly(self):
        """
        Given: A datetime at year boundary (New Year's Eve/Day)
        When: Converting to ISO UTC string
        Then: Handles the edge case correctly without date rollover issues
        """
        # Given - New Year's Eve
        dt_nye = datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        dt_nyd = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        # When
        result_nye = iso_utc(dt_nye)
        result_nyd = iso_utc(dt_nyd)
        
        # Then
        assert result_nye == "2023-12-31T23:59:59Z"
        assert result_nyd == "2024-01-01T00:00:00Z"


class TestEncodeCursor:
    def test_given_datetime_and_photo_id_when_encoding_then_returns_base64_string_that_can_be_decoded(self):
        """
        Given: A datetime and photo ID
        When: Encoding as cursor
        Then: Returns base64 string that can be decoded back to original values
        """
        # Given
        dt = datetime(2023, 12, 25, 10, 30, 45, tzinfo=timezone.utc)
        photo_id = "photo123"
        
        # When
        result = encode_cursor(dt, photo_id)
        
        # Then
        assert isinstance(result, str)
        assert len(result) > 0
        
        # And the cursor can be decoded back to original values
        decoded_dt, decoded_id = decode_cursor(result)
        assert decoded_dt == dt
        assert decoded_id == photo_id

    def test_given_photo_id_with_special_characters_when_encoding_then_preserves_all_characters(self):
        """
        Given: A photo ID containing special characters (hyphens, underscores, dots)
        When: Encoding as cursor
        Then: All special characters are preserved in the decoded result
        """
        # Given
        dt = datetime(2023, 12, 25, 10, 30, 45, tzinfo=timezone.utc)
        photo_id = "photo-123_test.jpg"
        
        # When
        result = encode_cursor(dt, photo_id)
        
        # Then
        decoded_dt, decoded_id = decode_cursor(result)
        assert decoded_dt == dt
        assert decoded_id == photo_id

    def test_given_naive_datetime_when_encoding_then_treats_as_utc_in_decoded_result(self):
        """
        Given: A naive datetime (no timezone)
        When: Encoding as cursor
        Then: Decoded datetime has UTC timezone applied
        """
        # Given
        dt = datetime(2023, 12, 25, 10, 30, 45)  # No timezone
        photo_id = "photo123"
        
        # When
        result = encode_cursor(dt, photo_id)
        
        # Then
        decoded_dt, decoded_id = decode_cursor(result)
        expected_dt = dt.replace(tzinfo=timezone.utc)
        assert decoded_dt == expected_dt
        assert decoded_id == photo_id


class TestDecodeCursor:
    def test_given_valid_encoded_cursor_when_decoding_then_returns_original_datetime_and_photo_id(self):
        """
        Given: A valid cursor encoded from datetime and photo ID
        When: Decoding the cursor
        Then: Returns the original datetime and photo ID
        """
        # Given
        dt = datetime(2023, 12, 25, 10, 30, 45, tzinfo=timezone.utc)
        photo_id = "photo123"
        cursor = encode_cursor(dt, photo_id)
        
        # When
        decoded_dt, decoded_id = decode_cursor(cursor)
        
        # Then
        assert decoded_dt == dt
        assert decoded_id == photo_id

    def test_given_cursor_with_microseconds_when_decoding_then_preserves_microsecond_precision(self):
        """
        Given: A cursor encoded from datetime with microseconds
        When: Decoding the cursor
        Then: Preserves microsecond precision in the decoded datetime
        """
        # Given
        dt = datetime(2023, 12, 25, 10, 30, 45, 123456, tzinfo=timezone.utc)
        photo_id = "photo123"
        cursor = encode_cursor(dt, photo_id)
        
        # When
        decoded_dt, decoded_id = decode_cursor(cursor)
        
        # Then
        assert decoded_dt == dt
        assert decoded_id == photo_id

    def test_given_invalid_base64_string_when_decoding_then_raises_exception(self):
        """
        Given: An invalid base64 string
        When: Attempting to decode as cursor
        Then: Raises an exception (ValueError or binascii.Error)
        """
        # Given
        invalid_cursor = "invalid_base64!"
        
        # When/Then
        with pytest.raises(Exception):  # Could be ValueError or binascii.Error
            decode_cursor(invalid_cursor)

    def test_given_valid_base64_without_pipe_separator_when_decoding_then_raises_value_error(self):
        """
        Given: Valid base64 string but without pipe separator in payload
        When: Attempting to decode as cursor
        Then: Raises ValueError due to missing separator
        """
        # Given
        import base64
        invalid_payload = "no_pipe_separator"
        invalid_cursor = base64.urlsafe_b64encode(invalid_payload.encode()).decode()
        
        # When/Then
        with pytest.raises(ValueError):
            decode_cursor(invalid_cursor)


class TestCursorRoundTrip:
    def test_given_various_datetime_and_photo_id_combinations_when_encoding_and_decoding_then_preserves_all_values(self):
        """
        Given: Various combinations of datetime and photo ID values including edge cases
        When: Encoding and then decoding each combination
        Then: All original values are preserved through the round trip
        """
        # Given
        test_cases = [
            (datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc), "photo1"),
            (datetime(2023, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc), "photo_with_long_name_123"),
            (datetime(2020, 2, 29, 12, 0, 0, tzinfo=timezone.utc), "leap_year_photo"),
        ]
        
        for dt, photo_id in test_cases:
            # When
            cursor = encode_cursor(dt, photo_id)
            decoded_dt, decoded_id = decode_cursor(cursor)
            
            # Then
            assert decoded_dt == dt
            assert decoded_id == photo_id