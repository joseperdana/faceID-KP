"""WIB day boundaries and the once-per-day attendance rule.

The service runs Saturday 17:00 WIB. Before core.timezone_wib existed, "today"
was a UTC calendar day in the check-in path, so the window 00:00-06:59 WIB
belonged to the previous UTC day and a member could be recorded twice for the
same WIB day.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from core.timezone_wib import (
    WIB,
    day_bounds_utc,
    parse_date,
    to_wib,
    wib_date_str,
    wib_hour,
)
from services import attendance_service
from services.db_service import DBService


# --- day boundaries -------------------------------------------------------

def test_day_bounds_cover_one_wib_day_in_utc():
    start, end = day_bounds_utc(date(2026, 9, 12))
    # Midnight WIB on the 12th is 17:00 UTC on the 11th.
    assert start.startswith("2026-09-11T17:00:00")
    assert end.startswith("2026-09-12T17:00:00")


@pytest.mark.parametrize(
    "moment_wib,expected_day",
    [
        # The case that produced duplicate check-ins: an early-morning arrival
        # is still "yesterday" in UTC but the same WIB day as the evening service.
        ("2026-09-12T06:30:00+07:00", "2026-09-12"),
        ("2026-09-12T17:05:00+07:00", "2026-09-12"),
        ("2026-09-12T23:59:59+07:00", "2026-09-12"),
        ("2026-09-13T00:00:30+07:00", "2026-09-13"),
    ],
)
def test_early_morning_and_evening_share_one_wib_day(moment_wib, expected_day):
    start, end = day_bounds_utc(parse_date(expected_day))
    moment_utc = datetime.fromisoformat(moment_wib).astimezone(timezone.utc).isoformat()
    assert start <= moment_utc < end
    assert wib_date_str(moment_utc) == expected_day


def test_bounds_are_half_open_so_midnight_belongs_to_one_day_only():
    _, end_of_12th = day_bounds_utc(date(2026, 9, 12))
    start_of_13th, _ = day_bounds_utc(date(2026, 9, 13))
    assert end_of_12th == start_of_13th


def test_wib_hour_converts_from_utc():
    # 10:05 UTC is 17:05 WIB — the service hour.
    assert wib_hour("2026-09-12T10:05:00+00:00") == 17


def test_naive_timestamps_are_treated_as_utc():
    """Rows written by earlier versions carry no offset."""
    assert to_wib("2026-09-12T10:05:00").hour == 17


def test_parse_date_rejects_garbage():
    with pytest.raises(ValueError):
        parse_date("12-09-2026")


# --- check-in behaviour ---------------------------------------------------

def _summary(total=3, last_seen="2026-09-05T10:00:00+00:00"):
    return {"total": total, "last_seen": last_seen}


def test_first_checkin_of_the_day_is_recorded():
    with patch.object(DBService, "check_user_log_today", return_value=[]), patch.object(
        DBService, "get_attendance_summary", return_value=_summary()
    ), patch.object(DBService, "insert_log") as insert:
        result = attendance_service.check_in(1, "Jonathan Kristi", "face", 0.81)

    assert result["status"] == "success"
    assert result["data"]["total_attendance"] == 4
    assert result["data"]["method"] == "face"
    assert result["data"]["similarity_score"] == 0.81
    insert.assert_called_once()
    assert insert.call_args[0][0]["method"] == "face"


def test_second_checkin_same_day_is_not_reported_as_success():
    """A duplicate must be distinguishable from a fresh check-in.

    Both used to return status "success", so the kiosk showed the same green
    modal either way and nobody could tell that the scan had recorded nothing.
    """
    existing = [{"id": 9, "timestamp": "2026-09-12T09:48:00+00:00", "method": "face"}]
    with patch.object(DBService, "check_user_log_today", return_value=existing), patch.object(
        DBService, "get_attendance_summary", return_value=_summary()
    ), patch.object(DBService, "insert_log") as insert:
        result = attendance_service.check_in(1, "Jonathan Kristi", "face")

    assert result["status"] == "already_checked_in"
    assert result["data"]["checked_in_at"] == "16:48"  # 09:48 UTC rendered in WIB
    insert.assert_not_called()


def test_unique_violation_is_treated_as_duplicate_not_error():
    """Closes the race between the check and the insert."""
    with patch.object(DBService, "check_user_log_today", return_value=[]), patch.object(
        DBService, "get_attendance_summary", return_value=_summary()
    ), patch.object(
        DBService, "insert_log", side_effect=Exception('duplicate key value violates unique constraint (23505)')
    ):
        result = attendance_service.check_in(1, "Jonathan Kristi", "manual")

    assert result["status"] == "already_checked_in"


def test_real_database_errors_still_propagate():
    with patch.object(DBService, "check_user_log_today", return_value=[]), patch.object(
        DBService, "get_attendance_summary", return_value=_summary()
    ), patch.object(DBService, "insert_log", side_effect=Exception("connection refused")):
        with pytest.raises(Exception, match="connection refused"):
            attendance_service.check_in(1, "Jonathan Kristi", "manual")


def test_never_attended_reports_baru_pertama():
    with patch.object(DBService, "check_user_log_today", return_value=[]), patch.object(
        DBService, "get_attendance_summary", return_value=_summary(total=0, last_seen=None)
    ), patch.object(DBService, "insert_log"):
        result = attendance_service.check_in(2, "Joanna Putri", "manual")

    assert result["data"]["last_seen"] == "Baru Pertama"
    assert result["data"]["total_attendance"] == 1


def test_check_in_queries_the_current_wib_day():
    """The bounds handed to the database must be WIB-derived, not UTC-derived."""
    captured = {}

    def fake_check(user_id, start_iso, end_iso):
        captured["start"] = start_iso
        captured["end"] = end_iso
        return []

    with patch.object(DBService, "check_user_log_today", side_effect=fake_check), patch.object(
        DBService, "get_attendance_summary", return_value=_summary()
    ), patch.object(DBService, "insert_log"):
        attendance_service.check_in(1, "Jonathan Kristi", "face")

    start = datetime.fromisoformat(captured["start"])
    end = datetime.fromisoformat(captured["end"])
    assert end - start == timedelta(days=1)
    # Midnight WIB, whatever the current UTC date happens to be.
    assert start.astimezone(WIB).hour == 0
    assert start.astimezone(WIB).minute == 0
