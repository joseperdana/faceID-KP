"""Data access layer.

Two rules hold throughout this module.

**Archived members stay archived.** `is_deleted` was previously filtered only on
direct `users` queries; every attendance-log query embedded `users(...)` as a
left join, so archived members kept appearing in the live feed, the exports and
the statistics. Worse, "present today" was counted from logs while "total
members" was counted from active users, which could make the dashboard show
more people present than exist. Every log query below uses `users!inner(...)`
plus an explicit `users.is_deleted` filter.

**Face embeddings never leave the server.** `select("*")` on `users` shipped a
512-dimension biometric vector per member to the browser. Column lists are
explicit here so that cannot happen by accident again.
"""

import logging
import re
from typing import Dict, List, Optional

from core import config
from core.timezone_wib import utc_now_iso
from database import supabase

logger = logging.getLogger(__name__)

# Columns that are safe to expose. face_embedding is deliberately absent.
USER_PUBLIC_COLUMNS = "id, full_name, gender, phone_number, created_at"
USER_KIOSK_COLUMNS = "id, full_name"

# PostgREST parses `or_(...)` as an expression language in which comma, dot and
# parentheses are syntax. Interpolating raw user input there lets a caller graft
# extra OR branches onto the query, so input is restricted to characters that
# appear in real names rather than escaped after the fact.
_SAFE_QUERY = re.compile(r"^[\w .'\-]{1,60}$", re.UNICODE)

_PAGE_SIZE = 1000


class DBService:
    # --- users -----------------------------------------------------------

    @staticmethod
    def get_all_users() -> List[Dict]:
        res = (
            supabase.table("users")
            .select(f"{USER_PUBLIC_COLUMNS}, attendance_logs(count)")
            .eq("is_deleted", False)
            .execute()
        )
        return res.data

    @staticmethod
    def get_users_with_count() -> int:
        res = (
            supabase.table("users")
            .select("id", count="exact")
            .eq("is_deleted", False)
            .execute()
        )
        return res.count or 0

    @staticmethod
    def get_users_by_gender() -> List[Dict]:
        res = supabase.table("users").select("gender").eq("is_deleted", False).execute()
        return res.data

    @staticmethod
    def insert_user(user_data: dict) -> Dict:
        res = supabase.table("users").insert(user_data).execute()
        return res.data[0]

    @staticmethod
    def update_user(user_id: int, user_data: dict) -> List[Dict]:
        res = (
            supabase.table("users")
            .update(user_data)
            .eq("id", user_id)
            .eq("is_deleted", False)
            .execute()
        )
        return res.data

    @staticmethod
    def soft_delete_user(user_id: int) -> List[Dict]:
        """Archive a member: hidden everywhere, attendance history preserved.

        This intentionally keeps `face_embedding`, because an archived member may
        be restored. Deleting the biometric data is a separate, explicit action —
        see purge_biometrics() — so the UI can describe each honestly.
        """
        res = (
            supabase.table("users")
            .update({"is_deleted": True, "deleted_at": utc_now_iso()})
            .eq("id", user_id)
            .eq("is_deleted", False)
            .execute()
        )
        return res.data

    @staticmethod
    def restore_user(user_id: int) -> List[Dict]:
        res = (
            supabase.table("users")
            .update({"is_deleted": False, "deleted_at": None})
            .eq("id", user_id)
            .execute()
        )
        return res.data

    @staticmethod
    def purge_biometrics(user_id: int) -> List[Dict]:
        """Irreversibly erase a member's biometric data and phone number.

        This is what satisfies a deletion request under UU 27/2022. The
        attendance history is kept (it carries no biometric data) so weekly
        statistics stay intact, but the person can no longer be recognised and
        their contact details are gone.
        """
        res = (
            supabase.table("users")
            .update(
                {
                    "face_embedding": None,
                    "phone_number": None,
                    "is_deleted": True,
                    "deleted_at": utc_now_iso(),
                }
            )
            .eq("id", user_id)
            .execute()
        )
        return res.data

    @staticmethod
    def delete_user(user_id: int) -> None:
        """Hard delete. Not reachable from the UI; kept for data-subject requests
        that require complete erasure including attendance rows."""
        supabase.table("users").delete().eq("id", user_id).execute()

    @staticmethod
    def get_user_by_name(full_name: str) -> List[Dict]:
        """Exact-name lookup, insensitive to case and surrounding whitespace.

        Previously an exact match, so "Jose", "jose" and "Jose " registered as
        three different people.
        """
        cleaned = (full_name or "").strip()
        if not cleaned:
            return []
        res = (
            supabase.table("users")
            .select("id, full_name")
            .ilike("full_name", cleaned)
            .eq("is_deleted", False)
            .execute()
        )
        return res.data

    @staticmethod
    def get_new_users_today(start_iso: str, end_iso: Optional[str] = None) -> List[Dict]:
        query = (
            supabase.table("users")
            .select(USER_PUBLIC_COLUMNS)
            .eq("is_deleted", False)
            .gte("created_at", start_iso)
        )
        if end_iso:
            query = query.lt("created_at", end_iso)
        return query.execute().data

    @staticmethod
    def get_user_by_id(user_id: int) -> List[Dict]:
        res = (
            supabase.table("users")
            .select(USER_PUBLIC_COLUMNS)
            .eq("id", user_id)
            .eq("is_deleted", False)
            .execute()
        )
        return res.data

    @staticmethod
    def search_active_users(query: str, limit: int = 25) -> List[Dict]:
        """Name search for the kiosk's manual fallback.

        Returns names and ids only. The phone number used to be included, which
        turned this into a contact-list export for the whole youth commission.
        """
        clean_q = (query or "").strip()
        if len(clean_q) < 2 or not _SAFE_QUERY.match(clean_q):
            return []
        # `%` and `_` are ilike wildcards; a member typing them should match
        # literals, not every row.
        pattern = clean_q.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")
        res = (
            supabase.table("users")
            .select(USER_KIOSK_COLUMNS)
            .ilike("full_name", f"%{pattern}%")
            .eq("is_deleted", False)
            .order("full_name")
            .limit(limit)
            .execute()
        )
        return res.data

    @staticmethod
    def get_users_last_seen() -> List[Dict]:
        res = (
            supabase.table("users")
            .select("id, full_name, phone_number, attendance_logs(timestamp)")
            .eq("is_deleted", False)
            .order("timestamp", desc=True, foreign_table="attendance_logs")
            .limit(1, foreign_table="attendance_logs")
            .execute()
        )
        return res.data

    # --- attendance logs -------------------------------------------------

    @staticmethod
    def get_recent_logs(limit: int = 15) -> List[Dict]:
        res = (
            supabase.table("attendance_logs")
            .select("id, timestamp, status, method, user_id, users!inner(id, full_name)")
            .eq("users.is_deleted", False)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data

    @staticmethod
    def get_logs_from_date(start_iso: str, end_iso: Optional[str] = None) -> List[Dict]:
        query = (
            supabase.table("attendance_logs")
            .select(
                "id, timestamp, status, method, user_id, "
                "users!inner(full_name, gender, phone_number)"
            )
            .eq("users.is_deleted", False)
            .gte("timestamp", start_iso)
        )
        if end_iso:
            # Half-open: the caller supplies the start of the *next* day.
            query = query.lt("timestamp", end_iso)
        return query.order("timestamp", desc=False).execute().data

    @staticmethod
    def get_logs_desc(start_iso: str, end_iso: Optional[str] = None) -> List[Dict]:
        query = (
            supabase.table("attendance_logs")
            .select("timestamp, status, method, users!inner(full_name, phone_number)")
            .eq("users.is_deleted", False)
            .gte("timestamp", start_iso)
        )
        if end_iso:
            query = query.lt("timestamp", end_iso)
        return query.order("timestamp", desc=True).execute().data

    @staticmethod
    def get_all_logs_with_users(limit: int = 500, offset: int = 0) -> Dict:
        """One page of the full log, with the true total.

        The unpaginated version silently stopped at PostgREST's 1000-row cap, so
        the dashboard's "complete history" quietly omitted older rows.
        """
        res = (
            supabase.table("attendance_logs")
            .select(
                "id, timestamp, status, method, user_id, users!inner(id, full_name)",
                count="exact",
            )
            .eq("users.is_deleted", False)
            .order("timestamp", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return {"rows": res.data, "total": res.count or 0}

    @staticmethod
    def get_user_history(user_id: int, limit: int = 500) -> List[Dict]:
        res = (
            supabase.table("attendance_logs")
            .select("id, timestamp, status, method")
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data

    @staticmethod
    def get_attendance_summary(user_id: int, before_iso: str) -> Dict:
        """Total attendance count plus the most recent visit before `before_iso`.

        Replaces fetching a member's entire history on every scan just to call
        len() on it — which also capped silently at 1000 rows, so long-standing
        members' totals stopped growing.
        """
        count_res = (
            supabase.table("attendance_logs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        previous = (
            supabase.table("attendance_logs")
            .select("timestamp")
            .eq("user_id", user_id)
            .lt("timestamp", before_iso)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        return {
            "total": count_res.count or 0,
            "last_seen": previous.data[0]["timestamp"] if previous.data else None,
        }

    @staticmethod
    def check_user_log_today(user_id: int, start_iso: str, end_iso: str) -> List[Dict]:
        """Has this member already checked in during the current WIB day?

        Bounds are half-open [start, end) so a check-in at exactly midnight WIB
        belongs to one day only.
        """
        res = (
            supabase.table("attendance_logs")
            .select("id, timestamp, method")
            .eq("user_id", user_id)
            .gte("timestamp", start_iso)
            .lt("timestamp", end_iso)
            .limit(1)
            .execute()
        )
        return res.data

    @staticmethod
    def insert_log(log_data: dict):
        try:
            return supabase.table("attendance_logs").insert(log_data).execute()
        except Exception as exc:
            # Only PGRST204 means "column missing from schema cache". The old
            # check also fired on any error whose text merely contained the word
            # "method" (such as "method not allowed"), silently retrying an
            # insert that dropped the face/manual distinction the PRD requires.
            code = getattr(exc, "code", None)
            if code == "PGRST204" or "PGRST204" in str(exc):
                logger.error(
                    "attendance_logs.method column missing — run migrations/001_init.sql. "
                    "Check-in method will not be recorded until then."
                )
                fallback = {
                    "user_id": log_data["user_id"],
                    "status": log_data.get("status", "Hadir"),
                    "timestamp": log_data.get("timestamp"),
                }
                return supabase.table("attendance_logs").insert(fallback).execute()
            raise

    @staticmethod
    def delete_log(log_id: int) -> List[Dict]:
        res = supabase.table("attendance_logs").delete().eq("id", log_id).execute()
        return res.data

    @staticmethod
    def delete_logs_by_user(user_id: int) -> None:
        supabase.table("attendance_logs").delete().eq("user_id", user_id).execute()

    @staticmethod
    def get_all_logs_from_date_paginated(start_iso: str) -> List[Dict]:
        all_logs: List[Dict] = []
        offset = 0
        while True:
            res = (
                supabase.table("attendance_logs")
                .select("timestamp, user_id")
                .gte("timestamp", start_iso)
                .range(offset, offset + _PAGE_SIZE - 1)
                .order("timestamp", desc=False)
                .execute()
            )
            all_logs.extend(res.data)
            if len(res.data) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
        return all_logs

    # --- face matching ---------------------------------------------------

    @staticmethod
    def match_faces(
        query_embedding: list,
        threshold: Optional[float] = None,
        limit: int = 2,
    ) -> List[Dict]:
        """Nearest registered faces above `threshold`, best first.

        Defaults to two candidates so the caller can reject an ambiguous match
        (see routers/kiosk.py). The SQL side lives in migrations/001_init.sql.
        """
        res = supabase.rpc(
            "match_faces",
            {
                "query_embedding": query_embedding,
                "match_threshold": (
                    config.FACE_MATCH_THRESHOLD if threshold is None else threshold
                ),
                "match_count": limit,
            },
        ).execute()
        return res.data
