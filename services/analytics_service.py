"""Dashboard statistics and Excel exports.

Everything here is computed on WIB calendar days. The previous version mixed
`datetime.now(timezone.utc).date()` for "today" and the trend buckets with WIB
boundaries in the daily export, so on a Sunday at 06:00 WIB the "Hadir Hari Ini"
card still showed Saturday's service and then dropped to zero an hour later.

Excel writing uses openpyxl directly. pandas was pulled in for two flat tables
and costs roughly 60 MB of RAM on a 2 GB VPS that also has to hold the face
recognition model.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List, Optional, Tuple

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from core.timezone_wib import (
    day_bounds_utc,
    now_wib,
    parse_date,
    to_wib,
    today_bounds_utc,
    today_wib,
    wib_date_str,
)
from services.db_service import DBService

logger = logging.getLogger(__name__)

_FILTER_DAYS = {"7d": 7, "30d": 30, "90d": 90}
_HEATMAP_DAYS = 365


def _period_bounds(filter_type: str) -> Tuple[str, str, int]:
    """UTC bounds covering whole WIB days for the requested period."""
    today = today_wib()
    if filter_type == "all":
        days = 1095  # three years; the heatmap covers the same span
    else:
        days = _FILTER_DAYS.get(filter_type, 30)
    start_day = today - timedelta(days=days - 1)
    start_utc, _ = day_bounds_utc(start_day)
    _, end_utc = day_bounds_utc(today)
    return start_utc, end_utc, days


def _method_of(log: Dict) -> str:
    method = (log.get("method") or "").lower()
    if method in ("face", "manual", "register"):
        return method
    return "unknown"


class AnalyticsService:
    # --- overview --------------------------------------------------------

    @staticmethod
    def calculate_dashboard_stats() -> Dict:
        start_utc, end_utc = today_bounds_utc()

        total_users = DBService.get_users_with_count()
        logs_today = DBService.get_logs_from_date(start_utc, end_utc)
        new_users_today = DBService.get_new_users_today(start_utc, end_utc)
        feed = DBService.get_recent_logs(15)

        method_counts = Counter(_method_of(log) for log in logs_today)

        return {
            "total_users": total_users,
            "present_today": len(logs_today),
            "new_users_today": len(new_users_today),
            "new_users_list": [
                {
                    "name": u["full_name"],
                    "phone": u.get("phone_number"),
                    "created_at": u.get("created_at"),
                }
                for u in new_users_today
            ],
            "recent_logs": feed,
            # Surfaces how often face recognition actually worked versus how
            # often somebody had to fall back to typing a name. The data was
            # already being written; nothing ever displayed it.
            "method_today": {
                "face": method_counts.get("face", 0),
                "manual": method_counts.get("manual", 0),
                "register": method_counts.get("register", 0),
                "unknown": method_counts.get("unknown", 0),
            },
            "generated_at": now_wib().isoformat(),
        }

    # --- analytics -------------------------------------------------------

    @staticmethod
    def get_analytics_data(filter_type: str, at_risk_days: int) -> Dict:
        start_utc, end_utc, days = _period_bounds(filter_type)
        logs_data = DBService.get_logs_from_date(start_utc, end_utc)

        today = today_wib()
        window = min(days, 365)
        date_counts: Dict[str, int] = {
            (today - timedelta(days=i)).isoformat(): 0 for i in range(window)
        }

        user_attendance: Counter = Counter()
        hour_counts: Counter = Counter()
        method_counts: Counter = Counter()
        gender_counts: Counter = Counter()
        seen_attendees: set = set()

        for log in logs_data:
            local = to_wib(log.get("timestamp"))
            if local is None:
                continue
            day_key = local.date().isoformat()
            if day_key in date_counts:
                date_counts[day_key] += 1
            hour_counts[f"{local.hour:02}:00"] += 1
            method_counts[_method_of(log)] += 1

            user = log.get("users") or {}
            name = user.get("full_name")
            if name:
                user_attendance[name] += 1
            # Gender ratio is computed over people who actually attended in the
            # selected period. Counting the users table instead produced a
            # figure that never changed when the period filter moved.
            user_id = log.get("user_id")
            if user_id is not None and user_id not in seen_attendees:
                seen_attendees.add(user_id)
                gender_counts[user.get("gender") or "unknown"] += 1

        sorted_dates = sorted(date_counts)
        trend_data = [date_counts[d] for d in sorted_dates]

        saturday_values = [
            count
            for day, count in zip(sorted_dates, trend_data)
            if datetime.fromisoformat(day).weekday() == 5 and count > 0
        ]
        avg_attendance = (
            round(sum(saturday_values) / len(saturday_values), 1) if saturday_values else 0
        )

        heatmap_start, _ = day_bounds_utc(today - timedelta(days=_HEATMAP_DAYS))
        heatmap_all: Dict[str, int] = defaultdict(int)
        for log in DBService.get_all_logs_from_date_paginated(heatmap_start):
            day_key = wib_date_str(log.get("timestamp"))
            if day_key:
                heatmap_all[day_key] += 1

        at_risk_list = AnalyticsService._build_at_risk(at_risk_days)

        attended = sum(gender_counts.values())
        pria = gender_counts.get("Pria", 0)
        wanita = gender_counts.get("Wanita", 0)
        unknown = attended - pria - wanita

        def pct(value: int) -> int:
            return round(value / attended * 100) if attended else 0

        # Rounding each share independently loses a point (33 + 33 + 33 = 99),
        # which is how the old chart could read "Pria 45% + Wanita 48%" with the
        # rest silently unaccounted for. The remainder is absorbed here so the
        # three shares always total 100.
        persen_pria = pct(pria)
        persen_wanita = pct(wanita)
        persen_unknown = (100 - persen_pria - persen_wanita) if attended else 0

        return {
            "filter_used": filter_type,
            "period_start": sorted_dates[0] if sorted_dates else None,
            "period_end": sorted_dates[-1] if sorted_dates else None,
            "trend": {"labels": sorted_dates, "data": trend_data},
            "heatmap_all": dict(heatmap_all),
            "avg_attendance": avg_attendance,
            "top_users": [{"name": n, "count": c} for n, c in user_attendance.most_common()],
            "peak_time": {k: v for k, v in sorted(hour_counts.items()) if v > 0},
            "at_risk": at_risk_list,
            "at_risk_days": at_risk_days,
            "method_stats": {
                "face": method_counts.get("face", 0),
                "manual": method_counts.get("manual", 0),
                "register": method_counts.get("register", 0),
                "unknown": method_counts.get("unknown", 0),
                "total": sum(method_counts.values()),
            },
            "gender_stats": {
                "basis": "kehadiran",
                "attendees": attended,
                "pria": pria,
                "wanita": wanita,
                "unknown": unknown,
                "persen_pria": persen_pria,
                "persen_wanita": persen_wanita,
                "persen_unknown": persen_unknown,
            },
            "generated_at": now_wib().isoformat(),
        }

    @staticmethod
    def _build_at_risk(at_risk_days: int) -> List[Dict]:
        now = now_wib()
        result: List[Dict] = []
        for user in DBService.get_users_last_seen():
            logs = user.get("attendance_logs") or []
            if not logs:
                result.append(
                    {
                        "name": user["full_name"],
                        "phone": user.get("phone_number"),
                        "days_absent": None,
                        "never_attended": True,
                    }
                )
                continue
            last_seen = to_wib(logs[0].get("timestamp"))
            if last_seen is None:
                continue
            days_absent = (now - last_seen).days
            if days_absent > at_risk_days:
                result.append(
                    {
                        "name": user["full_name"],
                        "phone": user.get("phone_number"),
                        "days_absent": days_absent,
                        "never_attended": False,
                    }
                )
        # Members who never attended sort first, then the longest absences.
        result.sort(key=lambda r: (not r["never_attended"], -(r["days_absent"] or 0)))
        return result

    # --- exports ---------------------------------------------------------

    @staticmethod
    def _write_sheet(rows: List[Dict], headers: List[str], sheet_name: str) -> BytesIO:
        workbook = Workbook()
        sheet = workbook.active
        # Excel rejects sheet names over 31 chars or containing []:*?/\
        sheet.title = sheet_name[:31]

        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True)

        for row in rows:
            sheet.append([row.get(header, "") for header in headers])

        for index, header in enumerate(headers, start=1):
            widest = max(
                [len(str(header))] + [len(str(row.get(header, ""))) for row in rows] or [0]
            )
            sheet.column_dimensions[get_column_letter(index)].width = min(widest + 4, 45)

        sheet.freeze_panes = "A2"

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return output

    @staticmethod
    def _rows_from_logs(logs: List[Dict], time_format: str) -> List[Dict]:
        rows = []
        for item in logs:
            local = to_wib(item.get("timestamp"))
            user = item.get("users") or {}
            rows.append(
                {
                    "Waktu (WIB)": local.strftime(time_format) if local else "-",
                    "Nama Lengkap": user.get("full_name", "Jemaat Diarsipkan"),
                    "No. HP": user.get("phone_number") or "-",
                    "Metode": {
                        "face": "Face ID",
                        "manual": "Manual",
                        "register": "Registrasi",
                    }.get(_method_of(item), "-"),
                    "Status": item.get("status", "Hadir"),
                }
            )
        return rows

    @staticmethod
    def generate_excel_report(filter_type: str) -> Tuple[BytesIO, str]:
        start_utc, end_utc, _ = _period_bounds(filter_type)
        logs = DBService.get_logs_desc(start_utc, end_utc)
        headers = ["Waktu (WIB)", "Nama Lengkap", "No. HP", "Metode", "Status"]
        output = AnalyticsService._write_sheet(
            AnalyticsService._rows_from_logs(logs, "%d-%m-%Y %H:%M:%S"),
            headers,
            "Laporan Absensi",
        )
        filename = f"Laporan_Absensi_{filter_type}_{today_wib().strftime('%Y%m%d')}.xlsx"
        return output, filename

    @staticmethod
    def generate_daily_excel_report(target_date: str) -> Tuple[BytesIO, str]:
        day = parse_date(target_date)
        start_utc, end_utc = day_bounds_utc(day)
        logs = DBService.get_logs_from_date(start_utc, end_utc)
        headers = ["Waktu (WIB)", "Nama Lengkap", "No. HP", "Metode", "Status"]
        output = AnalyticsService._write_sheet(
            AnalyticsService._rows_from_logs(logs, "%H:%M:%S"),
            headers,
            f"Absen {target_date}",
        )
        return output, f"Absensi_GKI_Bromo_{target_date}.xlsx"
