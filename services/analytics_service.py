from datetime import datetime, timezone, timedelta
import pandas as pd
from io import BytesIO
from services.db_service import DBService

class AnalyticsService:
    @staticmethod
    def calculate_dashboard_stats():
        today = datetime.now(timezone.utc).date().isoformat()
        total_users = DBService.get_users_with_count()
        logs_today = DBService.get_logs_from_date(today)
        new_users_today = DBService.get_new_users_today(today)
        feed = DBService.get_recent_logs(15)  # Increased from 5 — 5 rows disappears instantly at events

        return {
            "total_users": total_users,
            "present_today": len(logs_today),
            "new_users_today": len(new_users_today),
            "recent_logs": feed
        }

    @staticmethod
    def get_analytics_data(filter_type: str, at_risk_days: int):
        now = datetime.now(timezone.utc)
        if filter_type == "7d":
            start_date = (now - timedelta(days=7))
            days_count = 7
        elif filter_type == "90d":
            start_date = (now - timedelta(days=90))
            days_count = 90
        elif filter_type == "all":
            start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
            days_count = (now - start_date).days
        else:
            start_date = (now - timedelta(days=30))
            days_count = 30
            
        start_date_iso = start_date.isoformat()
        logs_data = DBService.get_logs_from_date(start_date_iso)

        date_counts = {}
        loop_range = min(days_count, 365) 
        for i in range(loop_range):
            d = (now - timedelta(days=i)).date().isoformat()
            date_counts[d] = 0
            
        for log in logs_data:
            d = log['timestamp'][:10]
            if d in date_counts:
                date_counts[d] += 1
        
        sorted_dates = sorted(date_counts.keys())
        trend_data = [date_counts[d] for d in sorted_dates]
        
        saturday_values = []
        for i, d_str in enumerate(sorted_dates):
            if datetime.fromisoformat(d_str).weekday() == 5: # 5 = Saturday
                saturday_values.append(trend_data[i])
                
        valid_saturdays = [v for v in saturday_values if v > 0]
        total_attendance = sum(valid_saturdays)
        active_days_count = len(valid_saturdays)
        avg_attendance = round(total_attendance / active_days_count, 1) if active_days_count > 0 else 0

        user_attendance_count = {}
        hour_counts = {f"{i:02}:00": 0 for i in range(24)}

        for log in logs_data:
            if log.get('users'):
                name = log['users']['full_name']
                user_attendance_count[name] = user_attendance_count.get(name, 0) + 1
            try:
                hour_utc = int(log['timestamp'][11:13]) 
                hour_wib = (hour_utc + 7) % 24
                hour_counts[f"{hour_wib:02}:00"] += 1
            except:
                pass

        top_users = sorted(user_attendance_count.items(), key=lambda x: x[1], reverse=True)
        peak_time_data = {k: v for k, v in hour_counts.items() if v > 0}
        
        all_users = DBService.get_all_users()
        all_logs_raw = DBService.get_logs_from_date((now - timedelta(days=3000)).isoformat()) 
        
        last_seen_map = {}
        heatmap_all = {}
        for log in all_logs_raw:
            uid = log['user_id']
            if uid not in last_seen_map or log['timestamp'] > last_seen_map[uid]:
                last_seen_map[uid] = log['timestamp']
            
            d = log['timestamp'][:10]
            heatmap_all[d] = heatmap_all.get(d, 0) + 1
        
        at_risk_list = []
        for user in all_users:
            uid = user['id']
            last_seen = last_seen_map.get(uid)
            
            is_missing = False
            days_missing = 0
            
            if not last_seen:
                is_missing = True
                days_missing = 999 
            else:
                last_date = datetime.fromisoformat(last_seen[:19]).replace(tzinfo=timezone.utc)
                delta = now - last_date
                if delta.days > at_risk_days:
                    is_missing = True
                    days_missing = delta.days
            
            if is_missing:
                at_risk_list.append({
                    "name": user['full_name'],
                    "phone": user['phone_number'],
                    "days_absent": days_missing
                })

        at_risk_list = sorted(at_risk_list, key=lambda x: x['days_absent'], reverse=True)
        
        users_gender = DBService.get_users_by_gender()
        total_users = len(users_gender)
        total_pria = sum(1 for u in users_gender if u.get("gender") == "Pria")
        total_wanita = sum(1 for u in users_gender if u.get("gender") == "Wanita")
        total_unknown = total_users - total_pria - total_wanita
        
        persentase_pria = round((total_pria / total_users * 100)) if total_users > 0 else 0
        persentase_wanita = round((total_wanita / total_users * 100)) if total_users > 0 else 0
        persentase_unknown = 100 - persentase_pria - persentase_wanita if total_users > 0 else 0

        return {
            "filter_used": filter_type,
            "trend": { "labels": sorted_dates, "data": trend_data },
            "heatmap_all": heatmap_all,
            "avg_attendance": avg_attendance,
            "top_users": [{"name": k, "count": v} for k, v in top_users],
            "peak_time": peak_time_data,
            "at_risk": at_risk_list,
            "gender_stats": {
                "pria": total_pria,
                "wanita": total_wanita,
                "unknown": total_unknown,
                "persen_pria": persentase_pria,
                "persen_wanita": persentase_wanita,
                "persen_unknown": persentase_unknown
            }
        }

    @staticmethod
    def generate_excel_report(filter_type: str) -> tuple[BytesIO, str]:
        now = datetime.now(timezone.utc)
        if filter_type == "7d":
            start_date = (now - timedelta(days=7))
        elif filter_type == "90d":
            start_date = (now - timedelta(days=90))
        elif filter_type == "all":
            start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        else:
            start_date = (now - timedelta(days=30))
            
        data_raw = DBService.get_logs_desc(start_date.isoformat())
        
        if not data_raw:
            df = pd.DataFrame(columns=["Waktu", "Nama Lengkap", "No. HP", "Status"])
        else:
            clean_data = []
            for item in data_raw:
                dt_utc = datetime.fromisoformat(item['timestamp'][:19]).replace(tzinfo=timezone.utc)
                dt_wib = dt_utc + timedelta(hours=7)
                formatted_time = dt_wib.strftime('%d-%m-%Y %H:%M:%S')
                user_info = item.get('users') or {"full_name": "User Terhapus", "phone_number": "-"}
                clean_data.append({
                    "Waktu Absen (WIB)": formatted_time,
                    "Nama Lengkap": user_info['full_name'],
                    "No. HP": user_info['phone_number'],
                    "Status Kehadiran": item['status']
                })
            df = pd.DataFrame(clean_data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Laporan Absensi')
        output.seek(0)

        filename = f"Laporan_Absensi_{filter_type}_{now.strftime('%Y%m%d')}.xlsx"
        return output, filename

    @staticmethod
    def generate_daily_excel_report(target_date: str) -> tuple[BytesIO, str]:
        wib_tz = timezone(timedelta(hours=7))
        start_wib = datetime.strptime(f"{target_date} 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=wib_tz)
        end_wib = datetime.strptime(f"{target_date} 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=wib_tz)
        
        start_utc = start_wib.astimezone(timezone.utc).isoformat()
        end_utc = end_wib.astimezone(timezone.utc).isoformat()

        data_raw = DBService.get_logs_from_date(start_utc, end_utc)
        
        if not data_raw:
            df = pd.DataFrame(columns=["Waktu Datang (WIB)", "Nama Lengkap", "No. HP", "Status Kehadiran"])
        else:
            clean_data = []
            for item in data_raw:
                dt_utc = datetime.fromisoformat(item['timestamp'][:19]).replace(tzinfo=timezone.utc)
                dt_wib = dt_utc + timedelta(hours=7)
                formatted_time = dt_wib.strftime('%H:%M:%S')
                user_info = item.get('users') or {"full_name": "User Terhapus", "phone_number": "-"}
                clean_data.append({
                    "Waktu Datang (WIB)": formatted_time,
                    "Nama Lengkap": user_info['full_name'],
                    "No. HP": user_info['phone_number'],
                    "Status Kehadiran": item['status']
                })
            df = pd.DataFrame(clean_data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f'Absen_{target_date}')
        output.seek(0)

        filename = f"Absensi_GKI_Bromo_{target_date}.xlsx"
        return output, filename
