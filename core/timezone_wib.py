"""Single source of truth for what "hari ini" means.

The fellowship runs Saturday 17:00 WIB (UTC+7). Before this module existed the
codebase held two competing definitions of a day: routers/kiosk.py and
services/analytics_service.py used `datetime.now(timezone.utc).date()`, while
routers/attendance.py correctly built WIB boundaries. Between 00:00 and 06:59
WIB those disagree, which allowed a member who checked in at 06:30 WIB (still
"yesterday" in UTC) to check in again at 17:05 WIB the same WIB day.

Every day-boundary computation in the application must go through here.
"""

from datetime import UTC, date, datetime, time, timedelta, timezone

WIB = timezone(timedelta(hours=7), name="WIB")


def now_wib() -> datetime:
    """Current moment expressed in WIB."""
    return datetime.now(UTC).astimezone(WIB)


def today_wib() -> date:
    """The calendar date it is right now in Malang."""
    return now_wib().date()


def day_bounds_utc(target: date) -> tuple[str, str]:
    """UTC ISO bounds [start, end) covering one full WIB calendar day.

    Half-open on purpose: use `.gte(start).lt(end)` so a log written at exactly
    midnight WIB belongs to one day only.
    """
    start_wib = datetime.combine(target, time.min, tzinfo=WIB)
    end_wib = start_wib + timedelta(days=1)
    return (
        start_wib.astimezone(UTC).isoformat(),
        end_wib.astimezone(UTC).isoformat(),
    )


def today_bounds_utc() -> tuple[str, str]:
    """UTC ISO bounds for the current WIB day."""
    return day_bounds_utc(today_wib())


def parse_date(target_date: str) -> date:
    """Parse a YYYY-MM-DD string, raising ValueError with a clear message."""
    try:
        return datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Format tanggal harus YYYY-MM-DD, dapat: {target_date!r}") from None


def to_wib(value: str | None) -> datetime | None:
    """Convert a stored ISO timestamp to WIB.

    Timestamps written by this application always carry an offset. Rows written
    by older versions may not; those are assumed to be UTC, which is what the
    previous code produced.
    """
    if not value:
        return None
    raw = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(raw[:19])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(WIB)


def wib_date_str(value: str | None) -> str | None:
    """The WIB calendar date (YYYY-MM-DD) a stored timestamp falls on."""
    converted = to_wib(value)
    return converted.date().isoformat() if converted else None


def wib_hour(value: str | None) -> int | None:
    """The WIB hour-of-day a stored timestamp falls on."""
    converted = to_wib(value)
    return converted.hour if converted else None


def utc_now_iso() -> str:
    """Timestamp for writing to the database — always stored in UTC."""
    return datetime.now(UTC).isoformat()
