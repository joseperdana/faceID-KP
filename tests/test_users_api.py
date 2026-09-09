"""Member management: partial updates, archiving, and biometric erasure."""

from unittest.mock import patch

from services.db_service import DBService


def test_user_list_never_includes_face_embeddings(admin_client):
    """`select("*")` used to ship a 512-float biometric vector per member."""
    rows = [
        {
            "id": 1,
            "full_name": "Jonathan Kristi",
            "gender": "Pria",
            "phone_number": "0812",
            "created_at": "2026-01-01T00:00:00+00:00",
            "attendance_logs": [{"count": 7}],
        }
    ]
    with patch.object(DBService, "get_all_users", return_value=rows):
        response = admin_client.get("/api/users")

    body = response.json()
    assert body["status"] == "success"
    user = body["data"][0]
    assert "face_embedding" not in user
    assert user["attendance_count"] == 7
    assert "attendance_logs" not in user


def test_update_sends_only_the_fields_that_were_supplied(admin_client):
    """Fixing a phone number must not rewrite gender.

    The edit form has no gender control and used to default to "Pria" whenever
    its client cache was cold, silently changing records and the commission's
    gender statistics along with them.
    """
    with patch.object(DBService, "update_user", return_value=[{"id": 1}]) as update:
        response = admin_client.put("/api/users/1", json={"phone_number": "08999"})

    assert response.status_code == 200
    assert update.call_args[0][1] == {"phone_number": "08999"}


def test_update_with_no_fields_is_rejected(admin_client):
    response = admin_client.put("/api/users/1", json={})
    assert response.status_code == 400


def test_update_of_a_missing_member_returns_404(admin_client):
    """Supabase returns an empty list rather than an error for a missing row."""
    with patch.object(DBService, "update_user", return_value=[]):
        response = admin_client.put("/api/users/999", json={"full_name": "Tidak Ada"})
    assert response.status_code == 404


def test_archive_reports_that_history_is_kept(admin_client):
    with patch.object(DBService, "soft_delete_user", return_value=[{"id": 1}]):
        response = admin_client.delete("/api/users/1")

    assert response.status_code == 200
    message = response.json()["message"]
    assert "arsip" in message.lower()
    assert "tetap tersimpan" in message.lower()


def test_archive_of_a_missing_member_returns_404(admin_client):
    with patch.object(DBService, "soft_delete_user", return_value=[]):
        assert admin_client.delete("/api/users/999").status_code == 404


def test_purge_biometrics_clears_the_embedding(admin_client):
    """Archiving alone left the face vector in the database forever."""
    captured = {}

    def fake_purge(user_id):
        captured["user_id"] = user_id
        return [{"id": user_id}]

    with patch.object(DBService, "purge_biometrics", side_effect=fake_purge):
        response = admin_client.delete("/api/users/1/biometrics")

    assert response.status_code == 200
    assert captured["user_id"] == 1
    assert "permanen" in response.json()["message"].lower()


def test_restore_brings_an_archived_member_back(admin_client):
    with patch.object(DBService, "restore_user", return_value=[{"id": 1}]):
        assert admin_client.post("/api/users/1/restore").status_code == 200


def test_delete_log_reports_404_when_nothing_was_removed(admin_client):
    with patch.object(DBService, "delete_log", return_value=[]):
        assert admin_client.delete("/api/logs/999").status_code == 404


def test_delete_log_succeeds(admin_client):
    with patch.object(DBService, "delete_log", return_value=[{"id": 3}]):
        assert admin_client.delete("/api/logs/3").status_code == 200


def test_all_logs_is_paginated_and_reports_the_true_total(admin_client):
    page = {"rows": [{"id": 1}], "total": 4321}
    with patch.object(DBService, "get_all_logs_with_users", return_value=page) as fetch:
        response = admin_client.get("/api/all-logs?limit=50&offset=100")

    body = response.json()
    assert body["total"] == 4321
    assert fetch.call_args[0] == (50, 100)


def test_dashboard_failure_returns_503_not_a_200_error_body(admin_client):
    """A 200 carrying {"status": "error"} makes uptime checks report health."""
    with patch(
        "services.analytics_service.AnalyticsService.calculate_dashboard_stats",
        side_effect=Exception("supabase down"),
    ):
        response = admin_client.get("/api/dashboard-stats")

    assert response.status_code == 503
    # The internal exception text must not reach the browser.
    assert "supabase down" not in response.text


def test_attendance_date_rejects_a_malformed_date(admin_client):
    assert admin_client.get("/api/attendance/date/12-09-2026").status_code == 400
