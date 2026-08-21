import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from datetime import datetime, timezone

client = TestClient(app)

def test_get_kiosk_page():
    """Verify that root URL serves the Kiosk attendance page."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_get_photobooth_page():
    """Verify that /photobooth serves the KP45 Indonesian Photobooth page."""
    response = client.get("/photobooth")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_search_users_for_manual_checkin():
    """Verify that public search endpoint returns matched users for manual fallback."""
    mock_users = [
        {"id": 1, "full_name": "Jonathan Kristi", "gender": "Pria", "phone_number": "081234567890"},
        {"id": 2, "full_name": "Joanna Putri", "gender": "Wanita", "phone_number": "081298765432"}
    ]
    with patch("services.db_service.DBService.search_active_users", return_value=mock_users):
        response = client.get("/api/users/search?q=Jo")
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["status"] == "success"
        assert len(json_data["data"]) == 2
        assert json_data["data"][0]["full_name"] == "Jonathan Kristi"

def test_manual_checkin_success():
    """Verify that manual check-in endpoint logs attendance with method='manual'."""
    user_id = 1
    mock_user = [{"id": 1, "full_name": "Jonathan Kristi"}]
    
    with patch("services.db_service.DBService.get_user_by_id", return_value=mock_user), \
         patch("services.db_service.DBService.check_user_log_today", return_value=[]), \
         patch("services.db_service.DBService.get_user_history", return_value=[]), \
         patch("services.db_service.DBService.insert_log") as mock_insert:
        
        response = client.post("/api/attendance/manual-checkin", data={"user_id": user_id})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "Jonathan Kristi" in data["message"]
        assert data["data"]["method"] == "manual"
        
        # Verify insert_log was called with method='manual'
        mock_insert.assert_called_once()
        inserted_data = mock_insert.call_args[0][0]
        assert inserted_data["user_id"] == 1
        assert inserted_data["method"] == "manual"

def test_manual_checkin_duplicate_same_day():
    """Verify that checking in twice on the same day returns friendly notice."""
    user_id = 1
    mock_user = [{"id": 1, "full_name": "Jonathan Kristi"}]
    mock_today_log = [{"id": 99, "user_id": 1, "timestamp": datetime.now(timezone.utc).isoformat()}]
    
    with patch("services.db_service.DBService.get_user_by_id", return_value=mock_user), \
         patch("services.db_service.DBService.check_user_log_today", return_value=mock_today_log), \
         patch("services.db_service.DBService.get_user_history", return_value=mock_today_log):
        
        response = client.post("/api/attendance/manual-checkin", data={"user_id": user_id})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "sudah absen hari ini" in data["message"]

def test_recognize_geofence_rejection():
    """Verify that coordinates outside 200m radius are blocked with 403."""
    response = client.post(
        "/api/recognize",
        data={"lat": -6.200000, "lng": 106.816666}, # Jakarta coordinates
        files={"file": ("test.jpg", b"fake image bytes", "image/jpeg")}
    )
    assert response.status_code == 403
    assert "Akses ditolak" in response.json()["message"]
