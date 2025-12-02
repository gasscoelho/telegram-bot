from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

__all__ = [
    "parse_duration",
    "format_duration",
    "as_apscheduler_date_args",
]

# Longest → shortest to ensure full consumption
# e.g. "1d", "2h", "30m", "1hr", "hours", "minutes"
_TOKEN_RE = re.compile(
    r"(?P<num>\d+)(?P<unit>"
    r"days|day|d|"
    r"hours|hour|hrs|hr|h|"
    r"minutes|minute|mins|min|m"
    r")",
    re.IGNORECASE,
)

# e.g. "7:04" (7h 4m), "1d7:04", "1d 7:04", "07:04"
_COLON_RE = re.compile(
    r"^(?:(?P<d>\d+)\s*d\s*)?(?P<h>\d{1,2}):(?P<m>\d{1,2})$",
    re.IGNORECASE,
)

_WHITESPACE_RE = re.compile(r"\s+")


def _compact(s: str) -> str:
    """Remove all whitespace (spaces, tabs, newlines) from a string."""
    return _WHITESPACE_RE.sub("", s)


def _parse_colon_form(s: str) -> timedelta | None:
    """Parse colon syntax like '1d7:04' or '7:04' into timedelta, else None."""
    compact = _compact(s)
    match = _COLON_RE.match(compact) or _COLON_RE.match(s)
    if not match:
        return None
    days = int(match.group("d") or 0)
    hours = int(match.group("h"))
    minutes = int(match.group("m"))
    if minutes >= 60:
        raise ValueError("Minutes must be < 60 in H:MM format")
    return timedelta(days=days, hours=hours, minutes=minutes)


def _parse_tokenized_form(s: str) -> timedelta | None:
    """Parse token syntax like '1d2h5m' or '1h30m' into timedelta, else None."""
    compact = _compact(s)
    days = hours = minutes = 0
    matched_total = 0
    found = False

    for match in _TOKEN_RE.finditer(compact):
        found = True
        matched_total += match.end() - match.start()
        num = int(match.group("num"))
        unit = match.group("unit").lower()
        if unit.startswith("d"):
            days += num
        elif unit.startswith("h"):
            hours += num
        elif unit.startswith("m"):
            minutes += num

    if not found:
        return None

    # Require full consumption: reject partial matches like '1m30'
    if matched_total != len(compact):
        return None

    # Minute overflow correction
    if minutes >= 60:
        hours += minutes // 60
        minutes %= 60

    return timedelta(days=days, hours=hours, minutes=minutes)


def _parse_bare_minutes(s: str) -> timedelta | None:
    """Parse plain integer minutes like '45' into timedelta, else None."""
    if s.isdigit():
        return timedelta(minutes=int(s))
    return None


def parse_duration(duration: str) -> timedelta:
    """
    Parse human-friendly duration into timedelta.
    Accepts token forms ('1h30m'), colon forms ('1d7:04'), or bare integer (minutes).
    """
    sanitized_duration = (duration or "").strip()
    if not sanitized_duration:
        raise ValueError("Empty duration")

    for parser in (_parse_colon_form, _parse_tokenized_form, _parse_bare_minutes):
        parsed_value = parser(sanitized_duration)
        if parsed_value is not None:
            return parsed_value

    raise ValueError(f"Could not parse duration: {sanitized_duration!r}")


def format_duration(td: timedelta) -> str:
    """
    Format a timedelta as 'Xd Yh Zm' (omitting zero units; ensures at least minutes).
    """
    total_minutes = int(td.total_seconds() // 60)
    d, rem = divmod(total_minutes, 1440)  # 24*60
    h, m = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m or not parts:
        parts.append(f"{m}m")
    return " ".join(parts)


def as_apscheduler_date_args(
    td: timedelta,
    *,  # Everything after this MUST be keyword-only
    now: datetime | None = None,
    tz: timezone | None = None,
) -> dict[str, datetime | str]:
    """
    Convert a relative timedelta into APScheduler 'date' trigger args (run once).

    Example:
        scheduler.add_job(func, **as_apscheduler_date_args(td, tz=timezone.utc))

    If tz is provided, 'now' will be interpreted in that timezone (default: UTC).
    """
    if td.total_seconds() <= 0:
        raise ValueError("Run date offset must be positive")

    if now is None:
        if tz is None:
            tz = UTC
        now = datetime.now(tz)
    run_at = now + td
    return {"trigger": "date", "run_date": run_at}
