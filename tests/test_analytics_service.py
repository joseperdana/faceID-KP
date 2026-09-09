"""Analytics: WIB bucketing, gender basis, and method ratio.

services/analytics_service.py had no tests at all, despite holding the most
timezone-sensitive code in the project.
"""

from unittest.mock import patch

import pytest

from core.timezone_wib import today_wib
from services.analytics_service import AnalyticsService
from services.db_service import DBService


def _log(timestamp, name="Jonathan Kristi", gender="Pria", method="face", user_id=1):
    return {
        "id": user_id,
        "timestamp": timestamp,
        "status": "Hadir",
        "method": method,
        "user_id": user_id,
        "users": {"full_name": name, "gender": gender, "phone_number": "0812"},
    }


def test_dashboard_counts_the_current_wib_day(admin_client=None):
    """The bounds passed to the database must span one WIB day."""
    captured = {}

    def fake_logs(start, end=None):
        captured["start"], captured["end"] = start, end
        return []

    with (
        patch.object(DBService, "get_users_with_count", return_value=10),
        patch.object(DBService, "get_logs_from_date", side_effect=fake_logs),
        patch.object(DBService, "get_new_users_today", return_value=[]),
        patch.object(DBService, "get_recent_logs", return_value=[]),
    ):
        AnalyticsService.calculate_dashboard_stats()

    from datetime import datetime, timedelta

    start = datetime.fromisoformat(captured["start"])
    end = datetime.fromisoformat(captured["end"])
    assert end - start == timedelta(days=1)


def test_dashboard_reports_the_face_versus_manual_ratio():
    """The data was always written; nothing ever displayed it.

    This ratio is the measurement that shows whether face recognition is
    actually working, or whether everyone is falling back to typing a name.
    """
    logs = [
        _log("2026-09-12T10:00:00+00:00", method="face"),
        _log("2026-09-12T10:01:00+00:00", method="face", user_id=2),
        _log("2026-09-12T10:02:00+00:00", method="manual", user_id=3),
        _log("2026-09-12T10:03:00+00:00", method=None, user_id=4),
    ]
    with (
        patch.object(DBService, "get_users_with_count", return_value=10),
        patch.object(DBService, "get_logs_from_date", return_value=logs),
        patch.object(DBService, "get_new_users_today", return_value=[]),
        patch.object(DBService, "get_recent_logs", return_value=[]),
    ):
        stats = AnalyticsService.calculate_dashboard_stats()

    assert stats["present_today"] == 4
    assert stats["method_today"] == {"face": 2, "manual": 1, "register": 0, "unknown": 1}


def test_gender_ratio_is_based_on_attendance_not_the_member_table():
    """It used to be computed from the users table.

    That figure never changed when the period filter moved, so the dashboard
    reported a "stable weekly ratio" that was really just the whole database.
    """
    today = today_wib().isoformat()
    logs = [
        _log(f"{today}T10:00:00+00:00", name="A", gender="Pria", user_id=1),
        _log(f"{today}T10:01:00+00:00", name="B", gender="Wanita", user_id=2),
        # Same person twice — must be counted once in the gender split.
        _log(f"{today}T11:00:00+00:00", name="A", gender="Pria", user_id=1),
        _log(f"{today}T11:01:00+00:00", name="C", gender=None, user_id=3),
    ]
    with (
        patch.object(DBService, "get_logs_from_date", return_value=logs),
        patch.object(DBService, "get_all_logs_from_date_paginated", return_value=[]),
        patch.object(DBService, "get_users_last_seen", return_value=[]),
        patch.object(DBService, "get_users_by_gender", return_value=[{"gender": "Pria"}] * 99),
    ):
        data = AnalyticsService.get_analytics_data("7d", 21)

    gender = data["gender_stats"]
    assert gender["basis"] == "kehadiran"
    assert gender["attendees"] == 3
    assert gender["pria"] == 1
    assert gender["wanita"] == 1
    assert gender["unknown"] == 1
    # Percentages must account for everyone, so the chart adds up to 100.
    assert gender["persen_pria"] + gender["persen_wanita"] + gender["persen_unknown"] == 100


def test_peak_hour_is_reported_in_wib():
    """17:00 WIB is the service hour; the same moment is 10:00 UTC."""
    today = today_wib().isoformat()
    logs = [_log(f"{today}T10:05:00+00:00")]
    with (
        patch.object(DBService, "get_logs_from_date", return_value=logs),
        patch.object(DBService, "get_all_logs_from_date_paginated", return_value=[]),
        patch.object(DBService, "get_users_last_seen", return_value=[]),
    ):
        data = AnalyticsService.get_analytics_data("7d", 21)

    assert data["peak_time"] == {"17:00": 1}


def test_heatmap_buckets_by_wib_date():
    """A 23:30 WIB check-in belongs to that WIB day, not the previous UTC one."""
    with (
        patch.object(DBService, "get_logs_from_date", return_value=[]),
        patch.object(
            DBService,
            "get_all_logs_from_date_paginated",
            # 16:30 UTC on the 12th is 23:30 WIB on the 12th.
            return_value=[{"timestamp": "2026-09-12T16:30:00+00:00", "user_id": 1}],
        ),
        patch.object(DBService, "get_users_last_seen", return_value=[]),
    ):
        data = AnalyticsService.get_analytics_data("30d", 21)

    assert data["heatmap_all"] == {"2026-09-12": 1}


def test_members_who_never_attended_are_listed_first():
    users = [
        {
            "id": 1,
            "full_name": "Lama",
            "phone_number": "0812",
            "attendance_logs": [{"timestamp": "2020-01-01T00:00:00+00:00"}],
        },
        {"id": 2, "full_name": "Belum Pernah", "phone_number": "0813", "attendance_logs": []},
    ]
    with (
        patch.object(DBService, "get_logs_from_date", return_value=[]),
        patch.object(DBService, "get_all_logs_from_date_paginated", return_value=[]),
        patch.object(DBService, "get_users_last_seen", return_value=users),
    ):
        data = AnalyticsService.get_analytics_data("30d", 21)

    at_risk = data["at_risk"]
    assert at_risk[0]["name"] == "Belum Pernah"
    assert at_risk[0]["never_attended"] is True
    # Rendered as "Belum pernah hadir", never the ungrammatical "Absen 999 hari".
    assert at_risk[0]["days_absent"] is None


def test_excel_export_includes_the_checkin_method():
    logs = [_log("2026-09-12T10:00:00+00:00", method="manual")]
    with patch.object(DBService, "get_logs_desc", return_value=logs):
        output, filename = AnalyticsService.generate_excel_report("7d")

    assert filename.endswith(".xlsx")
    from openpyxl import load_workbook

    sheet = load_workbook(output).active
    headers = [cell.value for cell in sheet[1]]
    assert "Metode" in headers
    assert sheet.cell(row=2, column=headers.index("Metode") + 1).value == "Manual"


def test_daily_export_renders_times_in_wib():
    logs = [_log("2026-09-12T10:05:00+00:00")]
    with patch.object(DBService, "get_logs_from_date", return_value=logs):
        output, filename = AnalyticsService.generate_daily_excel_report("2026-09-12")

    from openpyxl import load_workbook

    sheet = load_workbook(output).active
    assert sheet.cell(row=2, column=1).value == "17:05:00"
    assert "2026-09-12" in filename


def test_daily_export_rejects_a_malformed_date():
    with pytest.raises(ValueError):
        AnalyticsService.generate_daily_excel_report("12-09-2026")
