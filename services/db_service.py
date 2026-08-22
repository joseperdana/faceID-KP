from database import supabase
from typing import List, Dict, Optional

class DBService:
    @staticmethod
    def get_all_users() -> List[Dict]:
        # Filter out soft-deleted users from all normal queries.
        # Uses Postgrest nested select to count attendance logs, bypassing the 1000 limit.
        res = supabase.table("users").select("*, attendance_logs(count)").eq("is_deleted", False).execute()
        return res.data

    @staticmethod
    def get_users_with_count() -> int:
        res = supabase.table("users").select("id", count="exact").eq("is_deleted", False).execute()
        return res.count

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
        res = supabase.table("users").update(user_data).eq("id", user_id).execute()
        return res.data

    @staticmethod
    def soft_delete_user(user_id: int):
        """Soft delete: marks user as deleted without destroying data or attendance history."""
        from datetime import datetime, timezone
        supabase.table("users").update({
            "is_deleted": True,
            "deleted_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()

    @staticmethod
    def delete_user(user_id: int):
        """Hard delete — only used internally if needed. Prefer soft_delete_user() for UI actions."""
        supabase.table("users").delete().eq("id", user_id).execute()

    @staticmethod
    def get_user_by_name(full_name: str) -> List[Dict]:
        res = supabase.table("users").select("id").eq("full_name", full_name).eq("is_deleted", False).execute()
        return res.data

    @staticmethod
    def get_new_users_today(date_str: str) -> List[Dict]:
        res = supabase.table("users").select("*").gte("created_at", date_str).execute()
        return res.data

    @staticmethod
    def get_user_by_id(user_id: int) -> List[Dict]:
        res = supabase.table("users").select("id, full_name, gender, phone_number").eq("id", user_id).eq("is_deleted", False).execute()
        return res.data

    @staticmethod
    def search_active_users(query: str, limit: int = 25) -> List[Dict]:
        clean_q = query.strip()
        if not clean_q:
            return []
        res = supabase.table("users") \
            .select("id, full_name, gender, phone_number") \
            .or_(f"full_name.ilike.%{clean_q}%,phone_number.ilike.%{clean_q}%") \
            .eq("is_deleted", False) \
            .limit(limit) \
            .execute()
        return res.data

    @staticmethod
    def get_all_logs_raw() -> List[Dict]:
        res = supabase.table("attendance_logs").select("user_id").execute()
        return res.data

    @staticmethod
    def get_recent_logs(limit: int = 5) -> List[Dict]:
        res = supabase.table("attendance_logs").select("id, timestamp, status, users(full_name)").order("timestamp", desc=True).limit(limit).execute()
        return res.data

    @staticmethod
    def get_logs_from_date(start_iso: str, end_iso: Optional[str] = None) -> List[Dict]:
        query = supabase.table("attendance_logs").select("timestamp, status, user_id, users(full_name, gender, phone_number)").gte("timestamp", start_iso)
        if end_iso:
            query = query.lte("timestamp", end_iso)
        res = query.order("timestamp", desc=False).execute()
        return res.data

    @staticmethod
    def get_logs_desc(start_iso: str) -> List[Dict]:
        res = supabase.table("attendance_logs").select("timestamp, status, users(full_name, phone_number)").gte("timestamp", start_iso).order("timestamp", desc=True).execute()
        return res.data

    @staticmethod
    def get_all_logs_with_users() -> List[Dict]:
        res = supabase.table("attendance_logs").select("id, timestamp, status, users(full_name)").order("timestamp", desc=True).execute()
        return res.data
        
    @staticmethod
    def get_user_history(user_id: str) -> List[Dict]:
        res = supabase.table("attendance_logs").select("timestamp, status").eq("user_id", user_id).order("timestamp", desc=True).execute()
        return res.data

    @staticmethod
    def check_user_log_today(user_id: str, today_iso: str) -> List[Dict]:
        res = supabase.table("attendance_logs").select("*").eq("user_id", user_id).gte("timestamp", today_iso).execute()
        return res.data

    @staticmethod
    def insert_log(log_data: dict):
        try:
            return supabase.table("attendance_logs").insert(log_data).execute()
        except Exception as e:
            err_msg = str(e)
            # If the database schema does not yet have 'method' column (PGRST204), fallback to core columns
            if "method" in err_msg or "PGRST204" in err_msg:
                fallback_data = {
                    "user_id": log_data["user_id"],
                    "status": log_data.get("status", "Hadir"),
                    "timestamp": log_data.get("timestamp")
                }
                return supabase.table("attendance_logs").insert(fallback_data).execute()
            raise

    @staticmethod
    def delete_log(log_id: int):
        supabase.table("attendance_logs").delete().eq("id", log_id).execute()

    @staticmethod
    def delete_logs_by_user(user_id: int):
        supabase.table("attendance_logs").delete().eq("user_id", user_id).execute()

    @staticmethod
    def match_faces(query_embedding: list, threshold: float = 0.42, limit: int = 1) -> List[Dict]:
        res = supabase.rpc("match_faces", {
            "query_embedding": query_embedding,
            "match_threshold": threshold,
            "match_count": limit
        }).execute()
        return res.data

    @staticmethod
    def get_users_last_seen() -> List[Dict]:
        """Retrieves all users along with their single latest attendance log timestamp.
        Uses Postgrest nested ordering and limits to avoid fetching full history.
        """
        res = supabase.table("users") \
            .select("id, full_name, phone_number, attendance_logs(timestamp)") \
            .eq("is_deleted", False) \
            .order("timestamp", desc=True, foreign_table="attendance_logs") \
            .limit(1, foreign_table="attendance_logs") \
            .execute()
        return res.data

    @staticmethod
    def get_all_logs_from_date_paginated(start_iso: str) -> List[Dict]:
        """Paginates through attendance logs starting from a given date in chunks of 1000.
        This bypasses the Postgrest default 1000-row selection limit for all-time queries.
        """
        all_logs = []
        limit = 1000
        offset = 0
        while True:
            res = supabase.table("attendance_logs") \
                .select("timestamp, user_id") \
                .gte("timestamp", start_iso) \
                .range(offset, offset + limit - 1) \
                .order("timestamp", desc=False) \
                .execute()
            all_logs.extend(res.data)
            if len(res.data) < limit:
                break
            offset += limit
        return all_logs
