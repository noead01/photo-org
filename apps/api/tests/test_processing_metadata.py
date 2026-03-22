from datetime import UTC, datetime

from app.processing import metadata


def test_stat_timestamp_to_iso_drops_microseconds_and_uses_utc():
    result = metadata.stat_timestamp_to_iso(1_710_000_000.987654)

    expected = datetime.fromtimestamp(1_710_000_000, tz=UTC).isoformat()
    assert result == expected


def test_normalize_exif_datetime_supports_known_formats_and_rejects_invalid_values():
    assert metadata._normalize_exif_datetime("2024:03:21 10:11:12") == "2024-03-21T10:11:12+00:00"
    assert metadata._normalize_exif_datetime("2024-03-21 10:11:12") == "2024-03-21T10:11:12+00:00"
    assert metadata._normalize_exif_datetime("   ") is None
    assert metadata._normalize_exif_datetime("not-a-date") is None
    assert metadata._normalize_exif_datetime(None) is None


def test_extract_shot_timestamp_uses_subseconds_and_valid_offset():
    exif_map = {"DateTime": "2024:03:21 10:11:12"}
    exif_ifd = {
        "DateTimeOriginal": "2024:03:21 10:11:12",
        "SubsecTimeOriginal": "9876abc",
        "OffsetTimeOriginal": "+02:30",
    }

    result = metadata._extract_shot_timestamp(exif_map, exif_ifd)

    assert result == "2024-03-21T10:11:12.987600+02:30"


def test_extract_shot_timestamp_falls_back_to_utc_or_none():
    assert metadata._extract_shot_timestamp({"DateTime": "2024:03:21 10:11:12"}, {}) == (
        "2024-03-21T10:11:12+00:00"
    )
    assert metadata._extract_shot_timestamp({"DateTime": "bad-value"}, {}) is None
    assert metadata._extract_shot_timestamp({}, {}) is None


def test_shot_ts_source_prefers_datetime_original_then_datetime_then_generic_exif():
    shot_ts = "2024-03-21T10:11:12+00:00"

    assert metadata._shot_ts_source(shot_ts, {}, {"DateTimeOriginal": "x"}) == "exif:DateTimeOriginal"
    assert metadata._shot_ts_source(shot_ts, {"DateTime": "x"}, {}) == "exif:DateTime"
    assert metadata._shot_ts_source(shot_ts, {}, {}) == "exif"
    assert metadata._shot_ts_source(None, {"DateTime": "x"}, {"DateTimeOriginal": "x"}) is None


class _ExifWithIfd:
    def __init__(self, payload):
        self._payload = payload

    def get_ifd(self, ifd_id):
        return self._payload[ifd_id]


class _BrokenExif:
    def get_ifd(self, _ifd_id):
        raise RuntimeError("broken exif")


def test_read_ifd_returns_named_mapping_and_handles_missing_or_broken_interfaces():
    exif = _ExifWithIfd({0x8769: {1: "one", 2: "two"}})
    tag_names = {1: "One", 2: "Two"}

    assert metadata._read_ifd(exif, 0x8769, tag_names) == {"One": "one", "Two": "two"}
    assert metadata._read_ifd(object(), 0x8769, tag_names) == {}
    assert metadata._read_ifd(_BrokenExif(), 0x8769, tag_names) == {}


def test_gps_coordinate_and_altitude_handle_signs_and_invalid_values():
    assert metadata._gps_coordinate((10, 30, 0), "N") == 10.5
    assert metadata._gps_coordinate((10, 30, 0), "w") == -10.5
    assert metadata._gps_coordinate(None, "N") is None
    assert metadata._gps_coordinate(("bad", 30, 0), "N") is None

    assert metadata._gps_altitude(123.4567, 0) == 123.457
    assert metadata._gps_altitude(123.4567, 1) == -123.457
    assert metadata._gps_altitude(50, b"\x01") == -50.0
    assert metadata._gps_altitude("bad", 0) is None
    assert metadata._gps_altitude(None, 0) is None


def test_valid_offset_requires_full_iso8601_offset_shape():
    assert metadata._valid_offset("+02:30") is True
    assert metadata._valid_offset("-05:00") is True
    assert metadata._valid_offset("0230") is False
    assert metadata._valid_offset("UTC") is False
