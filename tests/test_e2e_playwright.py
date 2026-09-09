import re

from playwright.sync_api import BrowserContext, Page, expect

from core.security import COOKIE_NAME, create_access_token

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
    page.wait_for_timeout(300)  # wait debounce

    # Close modal
    btn_close = page.locator("#btn-close-manual-search")
    btn_close.click()
    expect(modal).to_have_class(re.compile(r"hidden"))


def test_photobooth_page_interactions(page: Page):
    """Test Nusantara Festive Light Photobooth UI controls, Landing Preview, 4 Layouts, 3s/5s Timers, and Stage transitions."""
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


def test_admin_dashboard_full_lifecycle_and_data_loading(page: Page, context: BrowserContext):
    """E2E Test ensuring dashboard loads all live data, stats, graphs, and handles tabs with 0 console errors."""
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    # Set authenticated admin cookie
    token = create_access_token(data={"sub": "admin"})
    context.add_cookies([{"name": COOKIE_NAME, "value": token, "domain": "127.0.0.1", "path": "/"}])

    # Navigate to Dashboard
    page.goto(f"{BASE_URL}/dashboard")
    expect(page).to_have_title(re.compile(r"Attendance Intelligence Hub|Dashboard|Presensi"))

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

    # Console errors are filtered rather than required to be zero.
    #
    # CI points at a nonexistent Supabase, so failed API calls are expected here
    # and the page is *supposed* to report them. A blanket "zero console errors"
    # assertion made this test fail for the correct behaviour, which is why it
    # could not be trusted. Only errors that indicate broken page code fail the
    # test.
    ignorable = ("Failed to load resource", "net::ERR_", "503", "Gagal memuat", "Layanan sedang")
    real_errors = [e for e in console_errors if not any(token in e for token in ignorable)]
    assert not real_errors, f"Dashboard had unexpected console errors: {real_errors}"


def test_dashboard_shows_an_error_state_when_the_api_fails(page: Page, context: BrowserContext):
    """A failed load must say so, not look like an empty church.

    Every dashboard loader used to swallow errors into console.error, leaving
    dashes in the KPI cards and empty tables — indistinguishable from "nobody
    has checked in yet".
    """
    token = create_access_token(data={"sub": "admin"})
    context.add_cookies([{"name": COOKIE_NAME, "value": token, "domain": "127.0.0.1", "path": "/"}])

    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_selector("#feed-table")
    # CI has no reachable database, so the feed must render a visible failure
    # with a retry affordance.
    expect(page.locator("#feed-table .js-retry")).to_be_visible(timeout=15000)


def test_kiosk_manual_fallback_is_wired_before_any_cdn_code_runs(page: Page):
    """The fallback button must work even if the AI libraries never load.

    `new FaceDetection(...)` used to run at the top level of index.js, so an
    unreachable CDN threw a ReferenceError that stopped the rest of the file —
    including the listener for this button. The kiosk's fallback silently became
    a dead control in exactly the situation it exists for.
    """
    # Block the CDN entirely to simulate the church hall losing its uplink.
    page.route("**/cdn.jsdelivr.net/**", lambda route: route.abort())
    page.goto(f"{BASE_URL}/")

    modal = page.locator("#manual-search-modal")
    page.locator("#btn-open-manual-search").click()
    expect(modal).not_to_have_class(re.compile(r"\bhidden\b"))


def test_register_page_requires_an_enrolled_device(page: Page):
    """/register is reachable from an enrolled kiosk or an admin, nobody else."""
    page.goto(f"{BASE_URL}/register")
    expect(page).to_have_url(f"{BASE_URL}/login")


def test_register_page_shows_the_consent_checkbox(page: Page, context: BrowserContext):
    """Biometric consent is mandatory and must be visible before capture."""
    token = create_access_token(data={"sub": "admin"})
    context.add_cookies([{"name": COOKIE_NAME, "value": token, "domain": "127.0.0.1", "path": "/"}])

    page.goto(f"{BASE_URL}/register")
    consent = page.locator("#consent")
    expect(consent).to_be_visible()
    assert consent.get_attribute("required") is not None
    expect(page.locator("#consent-wrapper")).to_contain_text("menyetujui")


def test_security_headers_are_served(page: Page):
    response = page.goto(f"{BASE_URL}/")
    headers = response.headers
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-content-type-options") == "nosniff"
    assert "frame-ancestors 'none'" in headers.get("content-security-policy", "")


def test_static_mount_does_not_serve_protected_pages(page: Page):
    """/static used to expose /static/dashboard.html with no session at all."""
    response = page.request.get(f"{BASE_URL}/static/dashboard.html")
    assert response.status == 404
