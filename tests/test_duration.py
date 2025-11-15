from datetime import timedelta

import pytest

from bot.utils.duration import format_duration, parse_duration


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
