from datetime import UTC, datetime, timedelta

import pytest

from src.shared.utils.duration import (
    format_duration,
    parse_duration,
    parse_server_time_to_duration,
)


@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("1h", timedelta(hours=1)),
        ("30m", timedelta(minutes=30)),
        ("1h30m", timedelta(hours=1, minutes=30)),
        ("1d 7:0", timedelta(days=1, hours=7)),
        ("1d7:04", timedelta(days=1, hours=7, minutes=4)),
        ("1d 7:04", timedelta(days=1, hours=7, minutes=4)),
        ("1d 7h 04m", timedelta(days=1, hours=7, minutes=4)),
        ("1d 7h 04min", timedelta(days=1, hours=7, minutes=4)),
        ("7:4", timedelta(hours=7, minutes=4)),
        ("90m", timedelta(hours=1, minutes=30)),
        ("1d2h5m", timedelta(days=1, hours=2, minutes=5)),
        ("1hr", timedelta(hours=1)),
        ("45", timedelta(minutes=45)),
        ("60m", timedelta(hours=1)),
        ("120m", timedelta(hours=2)),
        ("1h 60m", timedelta(hours=2)),
        ("07:04", timedelta(hours=7, minutes=4)),
        ("1d 0:59", timedelta(days=1, minutes=59)),
        ("1H30M", timedelta(hours=1, minutes=30)),
        ("1 hour 5 minutes", timedelta(hours=1, minutes=5)),
        ("2hours", timedelta(hours=2)),
        ("15mins", timedelta(minutes=15)),
        ("1d2h", timedelta(days=1, hours=2)),
        ("2h5m", timedelta(hours=2, minutes=5)),
        ("2h  5m", timedelta(hours=2, minutes=5)),
        ("\t 2h\n5m ", timedelta(hours=2, minutes=5)),
        ("0m", timedelta(minutes=0)),
    ],
)
def test_parse_duration_valid(input_str, expected):
    assert parse_duration(input_str) == expected


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "abc",
        "1d 7:64",
        "7:99",
        "007:04",
        "1m30",
        "4 8",
    ],
)
def test_parse_duration_invalid(bad):
    with pytest.raises(ValueError):
        parse_duration(bad)


@pytest.mark.parametrize(
    "td,expected",
    [
        (timedelta(minutes=0), "0m"),
        (timedelta(minutes=5), "5m"),
        (timedelta(hours=2), "2h"),
        (timedelta(hours=1, minutes=30), "1h 30m"),
        (timedelta(days=1, hours=7, minutes=4), "1d 7h 4m"),
        (timedelta(days=2), "2d"),
    ],
)
def test_format_duration_variants(td, expected):
    assert format_duration(td) == expected


@pytest.mark.parametrize(
    "server_time,now,expected",
    [
        # Time only - future today
        (
            "17:09",
            datetime(2025, 12, 3, 14, 0, tzinfo=UTC),
            timedelta(hours=3, minutes=9),
        ),
        # Time only - past today wraps to tomorrow
        (
            "17:09",
            datetime(2025, 12, 3, 18, 0, tzinfo=UTC),
            timedelta(hours=23, minutes=9),
        ),
        # Full date-time
        (
            "5-12-2025 17:09",
            datetime(2025, 12, 3, 14, 0, tzinfo=UTC),
            timedelta(days=2, hours=3, minutes=9),
        ),
        # Single digit day
        (
            "8-12-2025 10:00",
            datetime(2025, 12, 3, 14, 0, tzinfo=UTC),
            timedelta(days=4, hours=20),
        ),
        # Padded day
        (
            "08-12-2025 10:00",
            datetime(2025, 12, 3, 14, 0, tzinfo=UTC),
            timedelta(days=4, hours=20),
        ),
        # Midnight
        ("00:00", datetime(2025, 12, 3, 22, 0, tzinfo=UTC), timedelta(hours=2)),
        # Single digit hour
        (
            "3:30",
            datetime(2025, 12, 3, 1, 0, tzinfo=UTC),
            timedelta(hours=2, minutes=30),
        ),
    ],
)
def test_parse_server_time_valid(server_time, now, expected):
    assert parse_server_time_to_duration(server_time, now=now) == expected


def test_parse_server_time_uses_local_time_by_default():
    """Ensure parse_server_time_to_duration uses local time, not UTC.

    This is a regression test. If someone says "virar ministro às 10:00"
    and it's currently 9:00 local time, the duration should be ~1 hour,
    not 10+ hours (which would happen if UTC was used incorrectly).
    """
    # Get current local time
    local_now = datetime.now().astimezone()

    # Target: 30 minutes from now (in local time)
    target_time = local_now + timedelta(minutes=30)
    target_str = target_time.strftime("%H:%M")

    # Call without passing `now` - should use local time internally
    result = parse_server_time_to_duration(target_str)

    # Duration should be approximately 30 minutes (with some tolerance for test execution time)
    assert timedelta(minutes=29) <= result <= timedelta(minutes=31), (
        f"Server time '{target_str}' should be ~30 min from now. "
        f"Got {result}. This may indicate UTC is being used instead of local time."
    )


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        "   ",
        "abc",
        "25:00",  # invalid hour
        "12:60",  # invalid minute
        "17:9",  # minute must be 2 digits
        "1-1-2025",  # missing time
        "17:09:00",  # seconds not supported
        "1-12-2025 10:00",  # date in the past (assuming now > this)
    ],
)
def test_parse_server_time_invalid(invalid_input):
    """Invalid formats should raise ValueError."""
    now = datetime(2025, 12, 3, 14, 0, 0, tzinfo=UTC)
    with pytest.raises(ValueError):
        parse_server_time_to_duration(invalid_input, now=now)
