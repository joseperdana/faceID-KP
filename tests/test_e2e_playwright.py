import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, BrowserContext, expect
from core.security import create_access_token, COOKIE_NAME

# Bisa diarahkan ke port lain saat menjalankan E2E di laptop yang port 8000-nya
# sedang dipakai server pengembangan.
BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000")


def butuh_fitur(page: Page, key: str):
    """Lewati tes kalau fiturnya sedang dimatikan dari dashboard.

    Fitur yang sengaja dimatikan pengurus bukan kegagalan — memaksa tesnya merah
    membuat orang belajar mengabaikan suite yang merah.
    """
    try:
        data = page.request.get(f"{BASE_URL}/api/flags").json().get("data", {})
    except Exception:
        return
    if data.get(key) is False:
        pytest.skip(f"Fitur '{key}' sedang dimatikan dari dashboard.")

def test_kiosk_page_elements_and_manual_modal(page: Page, context: BrowserContext):
    """Test Kiosk root page and interactive manual search modal with geolocation granted."""
    context.grant_permissions(["geolocation"])
    context.set_geolocation({"latitude": -7.979261, "longitude": 112.625760})

    page.goto(f"{BASE_URL}/")
    
    # Check Title and Header
    expect(page).to_have_title("Absen Komisi Pemuda GKI Bromo")
    expect(page.locator("text=FaceID Absen KP")).to_be_visible()
    
    # Check Video element & status
    expect(page.locator("#video")).to_be_visible()
    expect(page.locator("#status-title")).to_be_visible()
    
    # Check Manual Search Modal interaction (initially hidden)
    modal = page.locator("#manual-search-modal")
    expect(modal).to_have_class(re.compile(r"hidden"))
    
    # Open Modal via top button
    btn_open = page.locator("#btn-open-manual-search")
    btn_open.click()
    expect(modal).not_to_have_class(re.compile(r"\bhidden\b"))
    
    # Type query in search
    search_input = page.locator("#manual-search-input")
    search_input.fill("Jonathan")
    page.wait_for_timeout(300) # wait debounce
    
    # Close modal
    btn_close = page.locator("#btn-close-manual-search")
    btn_close.click()
    expect(modal).to_have_class(re.compile(r"hidden"))

def test_photobooth_page_interactions(page: Page):
    """Test Nusantara Festive Light Photobooth UI controls, Landing Preview, 4 Layouts, 3s/5s Timers, and Stage transitions."""
    butuh_fitur(page, "photobooth")
    page.goto(f"{BASE_URL}/photobooth")
    
    # Check Page Header
    expect(page).to_have_title(re.compile(r"KP45|Photobooth"))
    expect(page.locator("text=KP45 PHOTOBOOTH")).to_be_visible()

    # Check Landing Page Camera Preview & Controls
    expect(page.locator("#preview-video")).to_be_visible()
    expect(page.locator("text=Preview Kamera")).to_be_visible()
    btn_mirror_welcome = page.locator("#btn-toggle-mirror-welcome")
    expect(btn_mirror_welcome).to_be_visible()
    btn_switch_welcome = page.locator("#btn-switch-cam-welcome")
    expect(btn_switch_welcome).to_be_visible()

    # Check Timer Selector on Welcome Stage (3s / 5s)
    timer_3s = page.locator("#timer-3s")
    timer_5s = page.locator("#timer-5s")
    expect(timer_3s).to_be_visible()
    expect(timer_5s).to_be_visible()
    expect(timer_3s).to_have_class(re.compile(r"bg-merdeka-navy"))

    # Switch to 5s timer
    timer_5s.click()
    expect(timer_5s).to_have_class(re.compile(r"bg-merdeka-navy"))
    expect(timer_3s).not_to_have_class(re.compile(r"bg-merdeka-navy"))

    # Switch back to 3s timer
    timer_3s.click()
    expect(timer_3s).to_have_class(re.compile(r"bg-merdeka-navy"))
    
    # Check 4 Layout Card selections on Welcome Stage
    layout_3strip = page.locator('[data-layout="3-strip"]')
    layout_4strip = page.locator('[data-layout="4-strip"]')
    layout_bento = page.locator('[data-layout="2x2-grid"]')
    layout_single = page.locator('[data-layout="single-wide"]')
    
    expect(layout_3strip).to_have_class(re.compile(r"layout-card-active"))
    
    # Click 4-Strip layout
    layout_4strip.click()
    expect(layout_4strip).to_have_class(re.compile(r"layout-card-active"))
    expect(layout_3strip).not_to_have_class(re.compile(r"layout-card-active"))
    
    # Click 2x2 Bento layout
    layout_bento.click()
    expect(layout_bento).to_have_class(re.compile(r"layout-card-active"))
    expect(layout_4strip).not_to_have_class(re.compile(r"layout-card-active"))

    # Click Single Wide layout
    layout_single.click()
    expect(layout_single).to_have_class(re.compile(r"layout-card-active"))
    
    # Switch back to 3-Strip
    layout_3strip.click()
    expect(layout_3strip).to_have_class(re.compile(r"layout-card-active"))
    
    # Check Custom Caption input in Result Modal
    caption_input = page.locator("#modal-custom-caption")
    expect(caption_input).to_be_attached()
    
    # Click Start Session Button -> Transitions to Camera Stage
    btn_start = page.locator("#btn-start-session")
    expect(btn_start).to_be_visible()
    btn_start.click()
    
    # Check Welcome stage hidden, Camera stage visible
    welcome_stage = page.locator("#welcome-stage")
    camera_stage = page.locator("#camera-stage")
    expect(welcome_stage).to_have_class(re.compile(r"hidden"))
    expect(camera_stage).not_to_have_class(re.compile(r"hidden"))

    # Check Viewfinder and Retake Quota Badge
    expect(page.locator("#video-stream")).to_be_visible()
    expect(page.locator("#retake-quota-badge")).to_be_visible()
    expect(page.locator("#retake-count-text")).to_contain_text("2x")
    expect(page.locator("#btn-retake-pose")).to_be_attached()
    expect(page.locator("#btn-next-pose")).to_be_attached()
    
    # Check Cancel button returns to Welcome stage
    btn_cancel = page.locator("#btn-cancel-session")
    btn_cancel.click()
    expect(welcome_stage).not_to_have_class(re.compile(r"hidden"))
    expect(camera_stage).to_have_class(re.compile(r"hidden"))

def test_photobooth_retake_flow_and_timer_interval(page: Page):
    """Test timer intervals, mirror toggle on preview, and retake quota state."""
    butuh_fitur(page, "photobooth")
    page.goto(f"{BASE_URL}/photobooth")

    # Verify initial mirror state
    preview_vid = page.locator("#preview-video")
    expect(preview_vid).to_have_class(re.compile(r"-scale-x-100"))

    # Toggle mirror on welcome stage
    btn_mirror = page.locator("#btn-toggle-mirror-welcome")
    btn_mirror.click()
    expect(preview_vid).not_to_have_class(re.compile(r"-scale-x-100"))

    # Select 5s timer
    btn_5s = page.locator("#timer-5s")
    btn_5s.click()
    expect(btn_5s).to_have_class(re.compile(r"bg-merdeka-navy"))

    # Start session
    page.locator("#btn-start-session").click()
    expect(page.locator("#camera-stage")).to_be_visible()
    expect(page.locator("#retake-count-text")).to_have_text("2x")
    expect(page.locator("#center-countdown")).to_be_attached()

    # Cancel session
    page.locator("#btn-cancel-session").click()
    expect(page.locator("#welcome-stage")).to_be_visible()

def test_photobooth_full_delivery_to_result_modal(page: Page):
    """Test that photobooth completes output processing, opens result modal, renders Stitch photostrip, and updates custom caption in real-time."""
    butuh_fitur(page, "photobooth")
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    page.goto(f"{BASE_URL}/photobooth")
    page.wait_for_load_state("networkidle")
    
    if errors:
        print(f"Page errors: {errors}")

    # Trigger full processAndDeliverOutputs with simulated canvas poses
    page.evaluate("""() => {
        const dummyCanvas = document.createElement('canvas');
        dummyCanvas.width = 640;
        dummyCanvas.height = 480;
        const ctx = dummyCanvas.getContext('2d');
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, 640, 480);
        
        window.__photobooth.setCapturedPoses([dummyCanvas, dummyCanvas, dummyCanvas]);
        window.__photobooth.processAndDeliverOutputs();
    }""")

    # Assert Result Modal is immediately visible
    result_modal = page.locator("#result-modal")
    expect(result_modal).to_be_visible()

    # Assert Stitch photostrip preview is visible
    stitch_wrapper = page.locator("#stitch-photostrip-wrapper")
    expect(stitch_wrapper).to_be_visible()

    # Assert Download button is ready
    btn_download = page.locator("#btn-download-strip")
    expect(btn_download).to_be_visible()

    # Test Live Custom Caption Input
    caption_input = page.locator("#modal-custom-caption")
    expect(caption_input).to_be_visible()
    caption_input.fill("Geng Pemuda Bromo 2026")
    expect(caption_input).to_have_value("Geng Pemuda Bromo 2026")

    # Assert live DOM preview text updates
    preview_message = page.locator("#strip-preview-message")
    expect(preview_message).to_have_text("Geng Pemuda Bromo 2026")

    # Close modal and verify return to welcome stage
    page.locator("#btn-retake").click()
    expect(result_modal).to_have_class(re.compile(r"hidden"))
    expect(page.locator("#welcome-stage")).to_be_visible()

def test_login_page_form(page: Page):
    """Test Admin login page."""
    page.goto(f"{BASE_URL}/login")
    expect(page.locator('input[type="password"]')).to_be_visible()
    expect(page.locator('button[type="submit"]')).to_be_visible()

def test_protected_routes_redirect_to_login(page: Page):
    """Verify that unauthenticated access to /dashboard redirects to /login."""
    page.goto(f"{BASE_URL}/dashboard")
    expect(page).to_have_url(f"{BASE_URL}/login")

# --- Data dashboard tanpa database sungguhan ---------------------------------
# CI tidak punya Supabase (kredensialnya palsu), jadi semua endpoint data
# dashboard membalas 500 dan tes ini tidak pernah bisa hijau di sana. Mengarahkan
# CI ke database produksi bukan pilihan: tes jangan pernah menyentuh data jemaat.
#
# Jawaban API di sini TIDAK ditulis tangan. Request dari browser diteruskan ke
# handler FastAPI yang asli, dijalankan di proses tes dengan DBService diganti
# data contoh. Jadi bentuk JSON-nya selalu sama dengan yang dihasilkan kode
# produksi (lihat pelajaran #2 di tasks/lessons.md), sementara HTML dan JS
# dashboard tetap datang dari server sungguhan.

DASHBOARD_DATA_ROUTES = (
    "**/api/dashboard-stats",
    "**/api/users",
    "**/api/users/*/history",
    "**/api/analytics*",
    "**/api/all-logs",
    "**/api/attendance/date/*",
)


def _sample_db():
    now = datetime.now(timezone.utc)
    iso = lambda days=0, hours=0: (now - timedelta(days=days, hours=hours)).isoformat()
    people = [
        {"id": 1, "full_name": "Contoh Satu", "gender": "Pria", "phone_number": "081200000001"},
        {"id": 2, "full_name": "Contoh Dua", "gender": "Wanita", "phone_number": "081200000002"},
        {"id": 3, "full_name": "Contoh Tiga", "gender": "Wanita", "phone_number": "081200000003"},
    ]
    users = [{**p, "created_at": iso(days=40 - p["id"]), "is_deleted": False,
              "lark_status": "linked", "attendance_logs": [{"count": 4 - p["id"]}]} for p in people]
    new_today = [{**people[2], "created_at": iso(hours=1)}]
    logs = [
        {"id": 10 + i, "timestamp": iso(days=d, hours=h), "status": "Hadir", "user_id": p["id"],
         "users": {"full_name": p["full_name"], "gender": p["gender"], "phone_number": p["phone_number"]}}
        for i, (p, d, h) in enumerate([(people[0], 0, 1), (people[1], 0, 2), (people[0], 7, 1), (people[2], 14, 1)])
    ]
    return {
        "get_users_with_count": lambda *a, **k: len(users),
        "get_all_users": lambda *a, **k: users,
        "get_users_by_gender": lambda *a, **k: [{"gender": u["gender"]} for u in users],
        "get_new_users_today": lambda *a, **k: new_today,
        "get_logs_from_date": lambda *a, **k: logs,
        "get_logs_desc": lambda *a, **k: logs,
        "get_recent_logs": lambda *a, **k: logs,
        "get_all_logs_with_users": lambda *a, **k: logs,
        "get_all_logs_from_date_paginated": lambda *a, **k: [
            {"timestamp": l["timestamp"], "user_id": l["user_id"]} for l in logs],
        "get_users_last_seen": lambda *a, **k: [
            {**p, "attendance_logs": [{"timestamp": l["timestamp"]} for l in logs if l["user_id"] == p["id"]]}
            for p in people],
        "get_user_history": lambda *a, **k: [{"timestamp": l["timestamp"], "status": l["status"]} for l in logs[:2]],
    }


@contextmanager
def dashboard_api_from_real_handlers(context: BrowserContext):
    from fastapi.testclient import TestClient
    from main import app

    with patch.multiple("services.db_service.DBService", **_sample_db()):
        client = TestClient(app)

        def forward(route):
            req = route.request
            url = urlsplit(req.url)
            target = url.path + (f"?{url.query}" if url.query else "")
            resp = client.request(
                req.method, target,
                headers={"cookie": req.headers.get("cookie", "")},
                content=req.post_data_buffer,
            )
            route.fulfill(
                status=resp.status_code,
                headers={"content-type": resp.headers.get("content-type", "application/json")},
                body=resp.content,
            )

        for pattern in DASHBOARD_DATA_ROUTES:
            context.route(pattern, forward)
        try:
            yield
        finally:
            for pattern in DASHBOARD_DATA_ROUTES:
                context.unroute(pattern)


def test_admin_dashboard_full_lifecycle_and_data_loading(page: Page, context: BrowserContext):
    """Dashboard memuat statistik, grafik, dan tab tanpa satu pun error konsol."""
    with dashboard_api_from_real_handlers(context):
        _run_dashboard_lifecycle(page, context)


def _run_dashboard_lifecycle(page: Page, context: BrowserContext):
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    # Set authenticated admin cookie
    token = create_access_token(data={"sub": "admin"})
    context.add_cookies([{
        "name": COOKIE_NAME,
        "value": token,
        "domain": "127.0.0.1",
        "path": "/"
    }])

    # Navigate to Dashboard
    page.goto(f"{BASE_URL}/dashboard")
    expect(page).to_have_title(re.compile(r"Attendance Intelligence Hub|Dashboard Presensi"))

    # 1. Overview Tab & Stats assertions
    page.wait_for_selector("#stat-total-users")
    page.wait_for_timeout(800)  # Wait for API fetch resolution

    stat_total = page.locator("#stat-total-users").inner_text()
    stat_present = page.locator("#stat-present-today").inner_text()
    stat_new = page.locator("#stat-new-today").inner_text()

    assert stat_total != "", "stat-total-users should not be empty"
    # Bukti data benar-benar mengalir dari handler asli: _sample_db berisi 3 anggota.
    assert re.sub(r"\D", "", stat_total) == "3", f"stat-total-users = {stat_total!r}"
    assert stat_present != "", "stat-present-today should not be empty"
    assert stat_new != "", "stat-new-today should not be empty"

    # Verify Feed Table renders
    expect(page.locator("#feed-table")).to_be_visible()

    # 2. Test Tab Switch to "Database Jemaat"
    page.locator("#btn-database").click()
    expect(page.locator("#database")).to_have_class(re.compile(r"active"))
    page.wait_for_timeout(600)
    expect(page.locator("#users-table")).to_be_visible()

    # Test Search filter in Database
    search_input = page.locator("#search-user")
    search_input.fill("a")
    page.wait_for_timeout(200)

    # 3. Test Tab Switch to "Statistik & Analytics"
    page.locator("#btn-analytics").click()
    expect(page.locator("#analytics")).to_have_class(re.compile(r"active"))
    page.wait_for_timeout(600)

    # Verify Charts and Analytics Stats
    expect(page.locator("#attendanceChart")).to_be_visible()
    expect(page.locator("#peakChart")).to_be_visible()
    expect(page.locator("#stat-avg")).to_be_visible()
    expect(page.locator("#stat-pria")).to_be_visible()
    expect(page.locator("#stat-wanita")).to_be_visible()

    # 4. Test Modals (All Logs Modal)
    page.evaluate("openAllLogsModal()")
    modal_all_logs = page.locator("#all-logs-modal")
    expect(modal_all_logs).not_to_have_class(re.compile(r"\bhidden\b"))
    page.wait_for_timeout(400)
    page.evaluate("closeAllLogsModal()")
    expect(modal_all_logs).to_have_class(re.compile(r"hidden"))

    # 5. Test Global Calendar Modal
    page.evaluate("openGlobalCalendarModal()")
    modal_cal = page.locator("#global-calendar-modal")
    expect(modal_cal).not_to_have_class(re.compile(r"\bhidden\b"))
    page.wait_for_timeout(400)
    page.evaluate("closeGlobalCalendarModal()")
    expect(modal_cal).to_have_class(re.compile(r"hidden"))

    # Assert 0 console errors occurred during entire dashboard session
    assert len(console_errors) == 0, f"Dashboard had console errors: {console_errors}"


def _stub_flags(context: BrowserContext, **overrides):
    """Paksa jawaban /api/flags supaya UI bisa diuji tanpa menyentuh tabel produksi."""
    import json
    data = {"geofence": False, "lark_handoff": True, "photobooth": True, "registration": True}
    data.update(overrides)
    context.unroute("**/api/flags")
    context.route("**/api/flags", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"status": "success", "data": data})))


def test_photobooth_button_follows_its_feature_flag(page: Page, context: BrowserContext):
    """Saklar mati harus menghilangkan pintu masuknya, bukan cuma mengunci rutenya.

    Tombol yang tetap ada tapi membuka 404 membuat orang mengira sistemnya rusak,
    padahal fiturnya memang sengaja dimatikan.
    """
    tombol = page.locator('a[href="/photobooth"]')

    _stub_flags(context, photobooth=True)
    page.goto(f"{BASE_URL}/")
    expect(tombol).to_be_visible()

    _stub_flags(context, photobooth=False)
    page.goto(f"{BASE_URL}/")
    expect(tombol).to_have_count(1)
    expect(tombol).to_be_hidden()


def test_registration_button_follows_its_feature_flag(page: Page, context: BrowserContext):
    tombol = page.locator('a[href="/register"]')

    _stub_flags(context, registration=False)
    page.goto(f"{BASE_URL}/")
    expect(tombol).to_be_hidden()


def test_kiosk_still_shows_every_button_when_flags_cannot_be_read(page: Page, context: BrowserContext):
    """Gagal membaca saklar tidak boleh menyembunyikan apa pun.

    Kalau daftar saklar tak terbaca, kiosk harus berperilaku seperti sebelum
    fitur saklar ada — bukan menyembunyikan fitur yang sebenarnya menyala.
    """
    context.unroute("**/api/flags")
    context.route("**/api/flags", lambda route: route.abort())
    page.goto(f"{BASE_URL}/")
    expect(page.locator('a[href="/photobooth"]')).to_be_visible()
    expect(page.locator('a[href="/register"]')).to_be_visible()
