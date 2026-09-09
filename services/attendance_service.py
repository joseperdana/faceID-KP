"""Shared check-in logic for both entry points.

`/api/recognize` and `/api/attendance/manual-checkin` used to carry ~60 near
identical lines each. They had already drifted: the "already checked in" branch
returned `method` in one and omitted it in the other, so the kiosk received
different shapes for the same condition. Any timezone fix also had to be made
twice. Both now call check_in() below.
"""

import logging
from typing import Dict, Optional

from core.timezone_wib import to_wib, today_bounds_utc, utc_now_iso
from services.db_service import DBService

logger = logging.getLogger(__name__)


def _format_last_seen(timestamp: Optional[str]) -> str:
    converted = to_wib(timestamp)
    return converted.strftime("%d %b %Y") if converted else "Baru Pertama"


def check_in(user_id: int, user_name: str, method: str, similarity: Optional[float] = None) -> Dict:
    """Record attendance for one member, once per WIB day.

    Returns a response envelope with an explicit status:
      * "success"            — attendance was recorded just now
      * "already_checked_in" — the member had already checked in today

    The caller must not collapse these two. Returning "success" for both is what
    made a rejected duplicate look identical to a fresh check-in on the kiosk,
    hiding misrecognition from the operator.
    """
    start_utc, end_utc = today_bounds_utc()

    existing = DBService.check_user_log_today(user_id, start_utc, end_utc)
    summary = DBService.get_attendance_summary(user_id, start_utc)
    total = summary["total"]
    last_seen = _format_last_seen(summary["last_seen"])

    def envelope(status: str, message: str, checked_in_at: Optional[str] = None) -> Dict:
        data = {
            "name": user_name,
            "total_attendance": total,
            "last_seen": last_seen,
            "method": method,
        }
        if similarity is not None:
            data["similarity_score"] = round(similarity, 2)
        if checked_in_at:
            converted = to_wib(checked_in_at)
            if converted:
                data["checked_in_at"] = converted.strftime("%H:%M")
        return {"status": status, "message": message, "data": data}

    if existing:
        row = existing[0]
        return envelope(
            "already_checked_in",
            f"{user_name} sudah tercatat hadir hari ini.",
            checked_in_at=row.get("timestamp"),
        )

    log_data = {
        "user_id": user_id,
        "status": "Hadir",
        "method": method,
        "timestamp": utc_now_iso(),
    }
    try:
        DBService.insert_log(log_data)
        total += 1
    except Exception as exc:
        # The unique constraint on (user_id, attendance_date) closes the race
        # between the check above and this insert: if two scans arrived at once,
        # the second lands here instead of creating a duplicate row.
        text = str(exc)
        if "23505" in text or "unique" in text.lower():
            return envelope("already_checked_in", f"{user_name} sudah tercatat hadir hari ini.")
        logger.exception("Failed to record attendance for user_id=%s", user_id)
        raise

    return envelope("success", f"Halo, {user_name}! Selamat datang.")
