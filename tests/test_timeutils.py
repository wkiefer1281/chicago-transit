from backend.utilities.timeutils import parse_cta_time


def test_bus_format_is_chicago_local():
    dt = parse_cta_time("20260715 14:30:05")  # CDT, UTC-5
    assert dt.utcoffset().total_seconds() == -5 * 3600
    assert dt.isoformat() == "2026-07-15T14:30:05-05:00"


def test_winter_offset_is_cst():
    assert parse_cta_time("20260115 14:30").utcoffset().total_seconds() == -6 * 3600


def test_train_iso_format():
    assert parse_cta_time("2026-07-15T14:30:05").hour == 14


def test_bad_values_return_none():
    assert parse_cta_time(None) is None
    assert parse_cta_time("") is None
    assert parse_cta_time("garbage") is None
