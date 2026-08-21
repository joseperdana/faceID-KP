import re
import pytest
from playwright.sync_api import Page, BrowserContext, expect

BASE_URL = "http://127.0.0.1:8000"

def test_kiosk_page_elements_and_manual_modal(page: Page, context: BrowserContext):
    """Test Kiosk root page and interactive manual search modal with geolocation granted."""
    # Grant geolocation permission to avoid blocking alert
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
    """Test KP45 Indonesian Photobooth UI controls, frames, and timers."""
    page.goto(f"{BASE_URL}/photobooth")
    
    # Check Page Header
    expect(page).to_have_title("Photobooth KP45 — Komisi Pemuda GKI Bromo")
    expect(page.locator("text=KP45 PHOTOBOOTH")).to_be_visible()
    
    # Check Frame selection
    frame_merah_putih = page.locator('[data-frame="merah-putih"]')
    frame_batik = page.locator('[data-frame="batik-gold"]')
    frame_polaroid = page.locator('[data-frame="retro-polaroid"]')
    
    expect(frame_merah_putih).to_have_class(re.compile(r"frame-active"))
    
    # Click Batik frame
    frame_batik.click()
    expect(frame_batik).to_have_class(re.compile(r"frame-active"))
    expect(frame_merah_putih).not_to_have_class(re.compile(r"frame-active"))
    
    # Click Polaroid frame
    frame_polaroid.click()
    expect(frame_polaroid).to_have_class(re.compile(r"frame-active"))
    expect(frame_batik).not_to_have_class(re.compile(r"frame-active"))
    
    # Check Timer toggle
    timer_5s = page.locator("#timer-5s")
    timer_5s.click()
    expect(timer_5s).to_have_class(re.compile(r"bg-rose-600"))
    
    # Check Custom Caption input
    caption_input = page.locator("#custom-caption-input")
    caption_input.fill("Geng Pemuda Bromo 2026")
    expect(caption_input).to_have_value("Geng Pemuda Bromo 2026")
    
    # Check Capture Button
    btn_capture = page.locator("#btn-capture")
    expect(btn_capture).to_be_visible()

def test_login_page_form(page: Page):
    """Test Admin login page."""
    page.goto(f"{BASE_URL}/login")
    expect(page.locator('input[type="password"]')).to_be_visible()
    expect(page.locator('button[type="submit"]')).to_be_visible()

def test_protected_routes_redirect_to_login(page: Page):
    """Verify that unauthenticated access to /dashboard redirects to /login."""
    page.goto(f"{BASE_URL}/dashboard")
    expect(page).to_have_url(f"{BASE_URL}/login")
