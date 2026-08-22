import re
import pytest
from playwright.sync_api import Page, BrowserContext, expect
from core.security import create_access_token, COOKIE_NAME

BASE_URL = "http://127.0.0.1:8000"

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
    """Test Nusantara Festive Light Photobooth UI controls, 4 Layouts, and Stage transitions."""
    page.goto(f"{BASE_URL}/photobooth")
    
    # Check Page Header
    expect(page).to_have_title(re.compile(r"Pesta Merdeka|Nusantara|Photobooth"))
    expect(page.locator("text=PESTA MERDEKA PHOTOBOOTH")).to_be_visible()
    
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
    
    # Check Custom Caption input
    caption_input = page.locator("#custom-caption-input")
    caption_input.fill("Geng Pemuda Bromo 2026")
    expect(caption_input).to_have_value("Geng Pemuda Bromo 2026")
    
    # Click Start Session Button -> Transitions to Camera Stage
    btn_start = page.locator("#btn-start-session")
    expect(btn_start).to_be_visible()
    btn_start.click()
    
    # Check Welcome stage hidden, Camera stage visible
    welcome_stage = page.locator("#welcome-stage")
    camera_stage = page.locator("#camera-stage")
    expect(welcome_stage).to_have_class(re.compile(r"hidden"))
    expect(camera_stage).not_to_have_class(re.compile(r"hidden"))
    
    # Check Cancel button returns to Welcome stage
    btn_cancel = page.locator("#btn-cancel-session")
    btn_cancel.click()
    expect(welcome_stage).not_to_have_class(re.compile(r"hidden"))
    expect(camera_stage).to_have_class(re.compile(r"hidden"))

def test_login_page_form(page: Page):
    """Test Admin login page."""
    page.goto(f"{BASE_URL}/login")
    expect(page.locator('input[type="password"]')).to_be_visible()
    expect(page.locator('button[type="submit"]')).to_be_visible()

def test_protected_routes_redirect_to_login(page: Page):
    """Verify that unauthenticated access to /dashboard redirects to /login."""
    page.goto(f"{BASE_URL}/dashboard")
    expect(page).to_have_url(f"{BASE_URL}/login")

def test_admin_dashboard_full_lifecycle_and_data_loading(page: Page, context: BrowserContext):
    """E2E Test ensuring dashboard loads all live data, stats, graphs, and handles tabs with 0 console errors."""
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
