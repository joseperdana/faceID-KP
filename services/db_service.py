from database import supabase
from typing import List, Dict, Optional

class DBService:
    @staticmethod
    def get_all_users() -> List[Dict]:
        res = supabase.table("users").select("*").execute()
        return res.data

    @staticmethod
    def get_users_with_count() -> int:
        res = supabase.table("users").select("id", count="exact").execute()
        return res.count

    @staticmethod
    def get_users_by_gender() -> List[Dict]:
        res = supabase.table("users").select("gender").execute()
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
    def delete_user(user_id: int):
        supabase.table("users").delete().eq("id", user_id).execute()

    @staticmethod
    def get_user_by_name(full_name: str) -> List[Dict]:
        res = supabase.table("users").select("id").eq("full_name", full_name).execute()
        return res.data

    @staticmethod
    def get_new_users_today(date_str: str) -> List[Dict]:
        res = supabase.table("users").select("*").gte("created_at", date_str).execute()
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
        supabase.table("attendance_logs").insert(log_data).execute()

    @staticmethod
    def delete_log(log_id: int):
        supabase.table("attendance_logs").delete().eq("id", log_id).execute()

    @staticmethod
    def delete_logs_by_user(user_id: int):
        supabase.table("attendance_logs").delete().eq("user_id", user_id).execute()

    @staticmethod
    def match_faces(query_embedding: list, threshold: float = 0.5, limit: int = 1) -> List[Dict]:
        res = supabase.rpc("match_faces", {
            "query_embedding": query_embedding,
            "match_threshold": threshold,
            "match_count": limit
        }).execute()
        return res.data
