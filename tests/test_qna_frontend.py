"""Uji halaman tanya jawab di browser sungguhan tanpa server dan tanpa database.

Semua request ke https://qna.test dijawab di sini: HTML/JS/CSS dibaca dari
frontend/qna, dan /api/qna/* dijawab FakeBackend yang menyimpan state di
memori. Yang diuji adalah perilaku halaman dan adapter, bukan server (server
diuji di test_qna_api.py, aturan bisnis di scripts/qna_selftest.sql).
https dipakai karena crypto.randomUUID hanya ada di secure context.
"""
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from playwright.sync_api import Page, Route, expect

ROOT = Path(__file__).resolve().parent.parent / "frontend" / "qna"
BASE = "https://qna.test"
PAGES = {"/tanya": "tanya.html", "/tanya/admin": "tanya-admin.html", "/tanya/display": "tanya-display.html"}


def ok(data):
    return 200, {"status": "success", "data": data}


def err(status, code, **extra):
    return status, {"status": "error", "code": code, "message": code, **extra}


class FakeBackend:
    def __init__(self):
        self.settings = {"session_open": True, "points_mode": "hiasan", "tts_engine": "browser",
                         "hidden": False, "show_nonce": 0}
        self.questions = []
        self.submitted = []

    def add(self, body, status="masuk", votes=0):
        qid = f"00000000-0000-4000-8000-{len(self.questions) + 1:012d}"
        self.questions.append({"id": qid, "body": body, "status": status, "votes": votes, "voters": set(),
                               "created_at": f"2026-11-14T10:00:{len(self.questions):02d}+00:00", "shown_at": None})
        return qid

    def _q(self, qid):
        return next(q for q in self.questions if q["id"] == qid)

    def act(self, qid, action, intro=None, sfx=None):
        q = self._q(qid)
        if action == "approve":
            q["status"] = "disetujui"
        elif action == "reject":
            q["status"] = "ditolak"
        elif action == "show":
            for other in self.questions:
                if other["status"] == "tampil":
                    other["status"] = "selesai"
            q["status"], q["shown_at"] = "tampil", "2026-11-14T11:00:00+00:00"
            q["intro"], q["sfx"] = intro, sfx
            self.settings.update(hidden=False, show_nonce=self.settings["show_nonce"] + 1)
        elif action == "done":
            q["status"] = "selesai"
            self.settings["show_nonce"] += 1

    def screen(self, action):
        self.settings.update(hidden=(action == "hide"), show_nonce=self.settings["show_nonce"] + 1)

    def display(self):
        q = next((q for q in self.questions if q["status"] == "tampil"), None)
        base = {"nonce": self.settings["show_nonce"], "tts_engine": self.settings["tts_engine"]}
        if not q or self.settings["hidden"]:
            return {**base, "question": None}
        votes = q["votes"] if self.settings["points_mode"] == "upvote" else None
        return {**base, "question": {
            "id": q["id"], "body": q["body"],
            "points_text": q.get("intro") or "Seseorang memberikan 50 poin!",
            "votes": votes, "sfx": q.get("sfx") or "ding",
        }}

    def public(self, device):
        items = [q for q in self.questions if q["status"] in ("disetujui", "tampil")]
        items.sort(key=lambda q: -q["votes"])
        return [{"id": q["id"], "body": q["body"], "votes": q["votes"], "voted": device in q["voters"],
                 "showing": q["status"] == "tampil"} for q in items]

    def handle(self, method, path, query, body):
        if path == "/api/qna/state":
            return ok({k: self.settings[k] for k in ("session_open", "points_mode")})
        if path == "/api/qna/questions" and method == "POST":
            if not self.settings["session_open"]:
                return err(409, "session_closed")
            self.submitted.append(body)
            return ok({"id": self.add(body["body"])})
        if path == "/api/qna/questions/public":
            return ok(self.public(query.get("device_id")))
        m = re.fullmatch(r"/api/qna/questions/([^/]+)/vote", path)
        if m:
            q = self._q(m.group(1))
            (q["voters"].add if body["on"] else q["voters"].discard)(body["device_id"])
            q["votes"] = len(q["voters"])
            return ok({"votes": q["votes"], "voted": body["on"]})
        if path == "/api/qna/display":
            return ok(self.display())
        if path == "/api/qna/admin/questions":
            return ok({"settings": dict(self.settings),
                       "questions": [{k: v for k, v in q.items() if k not in ("voters", "intro", "sfx")}
                                     for q in self.questions]})
        m = re.fullmatch(r"/api/qna/admin/questions/([^/]+)/(\w+)", path)
        if m:
            self.act(m.group(1), m.group(2), **(body or {}))
            return ok({"id": m.group(1), "action": m.group(2)})
        m = re.fullmatch(r"/api/qna/admin/screen/(\w+)", path)
        if m:
            self.screen(m.group(1))
            return ok(dict(self.settings))
        if path == "/api/qna/admin/settings":
            for key, value in body.items():
                if value is not None:
                    self.settings[key] = value
            return ok(dict(self.settings))
        if path == "/api/qna/admin/tts":
            return err(503, "tts_unavailable")
        return 404, {"detail": "tidak ada"}


def serve_static(route: Route, path: str) -> bool:
    if path in PAGES:
        route.fulfill(path=ROOT / PAGES[path])
        return True
    if path.startswith("/static/qna/"):
        route.fulfill(path=ROOT / path.removeprefix("/static/qna/"))
        return True
    return False


@pytest.fixture
def backend(page: Page):
    fake = FakeBackend()

    def handler(route: Route):
        req = route.request
        url = urlsplit(req.url)
        if serve_static(route, url.path):
            return
        if url.path == "/api/qna/admin/stream":
            # retry pendek: EventSource tersambung ulang terus, setiap hello = muat ulang.
            route.fulfill(status=200, content_type="text/event-stream", body="retry: 300\nevent: hello\ndata: {}\n\n")
            return
        body = json.loads(req.post_data) if req.post_data else None
        status, payload = fake.handle(req.method, url.path, dict(parse_qsl(url.query)), body)
        route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))

    page.route(f"{BASE}/**", handler)
    return fake


def test_jemaat_sends_question_then_cools_down(page: Page, backend):
    page.goto(f"{BASE}/tanya")
    page.fill("#body", "Gimana cara tahu panggilan hidup?")
    expect(page.locator("#count")).to_have_text("33/300")
    page.click("#send")
    expect(page.locator("#msg")).to_contain_text("Terkirim")
    expect(page.locator("#send")).to_be_disabled()
    expect(page.locator("#send")).to_contain_text("Tunggu")
    assert backend.submitted[0]["body"] == "Gimana cara tahu panggilan hidup?"
    assert re.fullmatch(r"[0-9a-f-]{36}", backend.submitted[0]["device_id"])


def test_jemaat_sees_closed_notice(page: Page, backend):
    backend.settings["session_open"] = False
    page.goto(f"{BASE}/tanya")
    expect(page.locator("#closed")).to_be_visible()
    expect(page.locator("#form")).to_be_hidden()


def test_tabs_hidden_in_hiasan_mode(page: Page, backend):
    page.goto(f"{BASE}/tanya")
    expect(page.locator("#form")).to_be_visible()
    expect(page.locator("#tabs")).to_be_hidden()


def test_upvote_lists_only_approved_and_toggles_vote(page: Page, backend):
    backend.settings["points_mode"] = "upvote"
    backend.add("Masih menunggu", "masuk")
    backend.add("Sudah disetujui", "disetujui")
    page.goto(f"{BASE}/tanya")
    page.click("[data-tab=daftar]")
    expect(page.locator(".qitem")).to_have_count(1)
    expect(page.locator(".qitem")).to_contain_text("Sudah disetujui")
    page.click(".vote")
    expect(page.locator(".vote span")).to_have_text("1")
    expect(page.locator(".vote")).to_have_class(re.compile(r"\bon\b"))
    page.click(".vote")
    expect(page.locator(".vote span")).to_have_text("0")


def test_question_text_is_escaped(page: Page, backend):
    backend.settings["points_mode"] = "upvote"
    backend.add('<img src=x onerror="window.__xss=1">', "disetujui")
    page.goto(f"{BASE}/tanya")
    page.click("[data-tab=daftar]")
    expect(page.locator(".qitem")).to_contain_text("<img src=x")
    assert page.evaluate("window.__xss") is None


def test_admin_moves_question_through_whole_flow(page: Page, backend):
    backend.add("Pertanyaan pertama")
    page.goto(f"{BASE}/tanya/admin")
    page.click("#col-masuk [data-act=approve]")
    expect(page.locator("#col-disetujui .qitem")).to_have_count(1)
    page.click("#col-disetujui [data-act=show]")
    expect(page.locator("#col-tampil .qitem")).to_contain_text("Pertanyaan pertama")
    assert backend.settings["show_nonce"] == 1
    page.click("#col-tampil [data-act=done]")
    expect(page.locator("#col-selesai .qitem")).to_have_count(1)
    expect(page.locator("#n-selesai")).to_have_text("1")


def test_admin_stream_reconnects_after_error_status(page: Page, backend):
    """Respons non-2xx (mis. nginx 502 saat restart) membuat EventSource
    tertutup permanen; tanpa sambung ulang manual, admin hanya mengandalkan
    poll 5 detik selama sisa acara."""
    stream_requests = []

    def flaky_stream(route):
        stream_requests.append(route.request.url)
        if len(stream_requests) == 1:
            route.fulfill(status=502, content_type="text/plain", body="Bad Gateway")
            return
        route.fallback()  # request berikutnya dilayani stub hello di fixture backend

    page.route(f"{BASE}/api/qna/admin/stream", flaky_stream)
    page.goto(f"{BASE}/tanya/admin")
    deadline_ms = 10000
    elapsed = 0
    while len(stream_requests) < 2 and elapsed < deadline_ms:
        page.wait_for_timeout(250)
        elapsed += 250
    assert len(stream_requests) >= 2, "EventSource tidak tersambung ulang setelah 502"


def test_admin_sorts_approved_by_votes_in_upvote_mode(page: Page, backend):
    backend.settings["points_mode"] = "upvote"
    backend.add("Sedikit", "disetujui", votes=1)
    backend.add("Banyak", "disetujui", votes=9)
    page.goto(f"{BASE}/tanya/admin")
    expect(page.locator("#col-disetujui .qitem").first).to_contain_text("Banyak")
    page.select_option("#sort", "time")
    expect(page.locator("#col-disetujui .qitem").first).to_contain_text("Sedikit")


def test_admin_locks_mode_while_session_open(page: Page, backend):
    page.goto(f"{BASE}/tanya/admin")
    expect(page.locator("#mode")).to_be_disabled()
    expect(page.locator("#session")).to_have_text("Tutup sesi")
    page.click("#session")
    expect(page.locator("#session")).to_have_text("Buka sesi")
    expect(page.locator("#mode")).to_be_enabled()
    assert backend.settings["session_open"] is False


def test_admin_screen_buttons(page: Page, backend):
    qid = backend.add("Tampil", "disetujui")
    backend.act(qid, "show")
    page.goto(f"{BASE}/tanya/admin")
    expect(page.locator("#conn")).to_have_class(re.compile(r"\bon\b"))
    with page.expect_response("**/api/qna/admin/screen/hide"):
        page.click("#hide")
    assert backend.settings["hidden"] is True
    with page.expect_response("**/api/qna/admin/screen/replay"):
        page.click("#replay")
    assert backend.settings["hidden"] is False


def test_admin_recovers_when_a_request_hangs(page: Page, backend):
    backend.add("Pertanyaan setelah macet", "masuk")
    page.add_init_script("window.QNA_REQUEST_TIMEOUT_MS = 300")
    hung = []

    def hang_first(route):
        if not hung:
            hung.append(route)  # sengaja tidak dijawab: meniru koneksi menggantung
            return
        route.fallback()

    page.route(f"{BASE}/api/qna/admin/questions", hang_first)
    page.goto(f"{BASE}/tanya/admin")
    expect(page.locator("#col-masuk .qitem")).to_contain_text("Pertanyaan setelah macet", timeout=10000)


def test_display_announces_shown_question_and_hides(page: Page, backend):
    qid = backend.add("Apa rasanya jadi pemuda di gereja?", "disetujui")
    page.goto(f"{BASE}/tanya/display?mode=overlay")
    expect(page.locator("body")).to_have_class(re.compile(r"\bmode-overlay\b"))
    page.click("#start")
    expect(page.locator("#setup")).to_be_hidden()
    expect(page.locator("#alert")).to_be_hidden()
    backend.act(qid, "show")
    # Bunyi notifikasi 1,2 detik + jeda polling/SSE.
    expect(page.locator("#qbody")).to_have_text("Apa rasanya jadi pemuda di gereja?", timeout=10000)
    expect(page.locator("#points")).to_have_text("Seseorang memberikan 50 poin!")
    backend.screen("hide")
    expect(page.locator("#alert")).to_be_hidden(timeout=10000)


def test_display_shows_current_question_silently_on_load(page: Page, backend):
    qid = backend.add("Sudah tampil sebelum laptop dinyalakan", "disetujui")
    backend.act(qid, "show")
    page.goto(f"{BASE}/tanya/display")
    expect(page.locator("body")).to_have_class(re.compile(r"\bmode-full\b"))
    page.click("#start")
    expect(page.locator("#qbody")).to_have_text("Sudah tampil sebelum laptop dinyalakan", timeout=5000)


RECORD_SPEECH = """
window.__spoken = [];
window.speechSynthesis.speak = (u) => { window.__spoken.push(u.text); setTimeout(() => u.onend && u.onend(), 50); };
window.speechSynthesis.cancel = () => {};
"""

# Setiap chime membuat 3 oscillator; menghitung oscillator = menghitung bunyi notifikasi.
COUNT_CHIMES = """
window.__oscillators = 0;
const realCreate = AudioContext.prototype.createOscillator;
AudioContext.prototype.createOscillator = function () {
  window.__oscillators += 1;
  return realCreate.call(this);
};
"""


def test_display_never_speaks_a_superseded_question(page: Page, backend):
    q1 = backend.add("Pertanyaan pertama yang terlambat", "disetujui")
    q2 = backend.add("Pertanyaan kedua yang menggantikan", "disetujui")
    backend.settings["tts_engine"] = "cloud"
    page.add_init_script(RECORD_SPEECH)
    page.goto(f"{BASE}/tanya/display")
    page.click("#start")
    # Sync awal (senyap) sudah selesai saat #conn menyala; show setelahnya.
    expect(page.locator("#conn")).to_have_class(re.compile(r"\bon\b"))
    # Suara cloud lambat dan akhirnya gagal: pemanggil jatuh ke suara browser.
    page.evaluate("QnaApi.tts = () => new Promise((resolve) => setTimeout(() => resolve(null), 1500))")
    backend.act(q1, "show")
    expect(page.locator("#qbody")).to_have_text("Pertanyaan pertama yang terlambat", timeout=10000)
    backend.act(q2, "show")  # selagi suara q1 masih ditunggu
    page.wait_for_function("window.__spoken.some((t) => t.includes('kedua'))", timeout=15000)
    spoken = page.evaluate("window.__spoken")
    assert not any("pertama" in t for t in spoken), spoken


def test_display_ignores_out_of_order_responses(page: Page, backend):
    qid = backend.add("Jangan muncul lagi setelah dikosongkan", "disetujui")
    page.add_init_script(RECORD_SPEECH)
    page.add_init_script(COUNT_CHIMES)
    page.goto(f"{BASE}/tanya/display")
    page.click("#start")
    # Sync awal (senyap) sudah selesai saat #conn menyala; show setelahnya,
    # supaya show benar-benar lewat jalur pengumuman (bunyi + kartu).
    expect(page.locator("#conn")).to_have_class(re.compile(r"\bon\b"))
    backend.act(qid, "show")
    expect(page.locator("#qbody")).to_have_text("Jangan muncul lagi setelah dikosongkan", timeout=10000)
    # Kartu muncul hanya setelah chime selesai, jadi di titik ini tepat satu chime.
    assert page.evaluate("window.__oscillators") == 3
    # Jawaban display() berikutnya (yang masih memuat pertanyaan tampil) ditahan
    # 1,5 detik: meniru respons lama yang datang setelah layar dikosongkan.
    page.evaluate("""() => {
      const original = QnaApi.display;
      window.__delayNext = true;
      QnaApi.display = async () => {
        const d = await original();
        if (window.__delayNext) {
          window.__delayNext = false;
          window.__delayedStarted = true;
          await new Promise((r) => setTimeout(r, 1500));
        }
        return d;
      };
    }""")
    page.wait_for_function("window.__delayedStarted === true", timeout=5000)
    backend.screen("hide")
    expect(page.locator("#alert")).to_be_hidden(timeout=10000)
    page.wait_for_timeout(4000)  # jendela pengamatan: jawaban lama tiba di sini
    # Satu chime saja. Respons lama yang mengumumkan ulang menambah 3 oscillator lagi.
    assert page.evaluate("window.__oscillators") == 3


SB = "https://sb.test"
FALLBACK_CONFIG = f"""window.QNA_CONFIG = {{
  backend: "supabase", supabaseUrl: "{SB}", supabaseKey: "sb_publishable_uji",
  pages: {{ jemaat: "/", admin: "/admin.html", display: "/display.html" }},
}};"""


@pytest.fixture
def fallback(page: Page):
    """Halaman yang sama, tapi config.js menunjuk adapter Supabase."""
    calls = []
    state = {"session_open": True, "points_mode": "hiasan", "tts_engine": "browser", "hidden": False, "show_nonce": 0}
    questions = []

    def site(route: Route):
        path = urlsplit(route.request.url).path
        if path == "/static/qna/config.js":
            route.fulfill(content_type="application/javascript", body=FALLBACK_CONFIG)
        elif not serve_static(route, {"/": "/tanya", "/admin.html": "/tanya/admin"}.get(path, path)):
            route.fulfill(status=404, body="")

    def rpc(route: Route):
        fn = urlsplit(route.request.url).path.rsplit("/", 1)[-1]
        args = json.loads(route.request.post_data or "{}")
        calls.append((fn, args, route.request.headers.get("apikey")))
        if fn.startswith("qna_admin") and args.get("p_pin") != "pin-uji-panjang":
            return route.fulfill(status=400, content_type="application/json",
                                 body=json.dumps({"code": "P0001", "message": "forbidden"}))
        if fn == "qna_state":
            body = {k: state[k] for k in ("session_open", "points_mode")}
        elif fn == "qna_submit":
            if any(a.get("p_device") == args["p_device"] for f, a, _ in calls[:-1] if f == "qna_submit"):
                return route.fulfill(status=400, content_type="application/json",
                                     body=json.dumps({"code": "P0001", "message": "cooldown:17"}))
            questions.append(args["p_body"])
            body = {"id": "00000000-0000-4000-8000-000000000001"}
        elif fn == "qna_admin_list":
            body = {"settings": state, "questions": [
                {"id": "00000000-0000-4000-8000-000000000001", "body": b, "status": "masuk",
                 "created_at": "2026-11-14T10:00:00+00:00", "shown_at": None, "votes": 0} for b in questions]}
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route(f"{BASE}/**", site)
    page.route(f"{SB}/rest/v1/rpc/**", rpc)
    return calls


def test_fallback_jemaat_submits_via_rpc_and_maps_cooldown(page: Page, fallback):
    page.goto(f"{BASE}/")
    page.fill("#body", "Pertanyaan lewat jalur cadangan")
    page.click("#send")
    expect(page.locator("#msg")).to_contain_text("Terkirim")
    fn, args, apikey = next(c for c in fallback if c[0] == "qna_submit")
    assert args["p_body"] == "Pertanyaan lewat jalur cadangan"
    assert apikey == "sb_publishable_uji"
    page.reload()  # device_id tetap sama (localStorage), jadi jeda harus terpicu
    page.fill("#body", "Kedua kalinya")
    page.click("#send")
    expect(page.locator("#send")).to_contain_text("Tunggu")


def test_fallback_admin_requires_pin(page: Page, fallback):
    page.goto(f"{BASE}/admin.html")
    expect(page.locator("#login")).to_be_visible()
    page.fill("#pin", "salah")
    page.click("#login button")
    expect(page.locator("#loginMsg")).to_have_text("PIN salah.")
    page.fill("#pin", "pin-uji-panjang")
    page.click("#login button")
    expect(page.locator("#app")).to_be_visible()
    expect(page.locator("#linkOverlay")).to_have_attribute("href", "/display.html?mode=overlay")


def test_jemaat_success_message_is_short(page: Page, backend):
    page.goto(f"{BASE}/tanya")
    page.fill("#body", "Pertanyaan singkat saja")
    page.click("#send")
    expect(page.locator("#msg")).to_have_text("Terkirim!")


def test_admin_show_sends_chosen_intro_and_sfx(page: Page, backend):
    qid = backend.add("Pilih pesan pembuka", "disetujui")
    page.goto(f"{BASE}/tanya/admin")
    page.select_option("#intro", "Seorang anak Tuhan bertanya")
    page.select_option("#sfx", "tada")
    with page.expect_response("**/api/qna/admin/questions/*/show"):
        page.click("#col-disetujui [data-act=show]")
    q = backend._q(qid)
    assert (q["intro"], q["sfx"]) == ("Seorang anak Tuhan bertanya", "tada")


def test_admin_show_with_custom_intro(page: Page, backend):
    qid = backend.add("Pesan buatan admin", "disetujui")
    page.goto(f"{BASE}/tanya/admin")
    expect(page.locator("#introCustom")).to_be_hidden()
    page.select_option("#intro", "__custom")
    page.fill("#introCustom", "Pertanyaan dari barisan belakang!")
    with page.expect_response("**/api/qna/admin/questions/*/show"):
        page.click("#col-disetujui [data-act=show]")
    assert backend._q(qid)["intro"] == "Pertanyaan dari barisan belakang!"


def test_admin_random_defaults_pick_from_the_lists(page: Page, backend):
    qid = backend.add("Biarkan acak", "disetujui")
    page.goto(f"{BASE}/tanya/admin")
    intros = page.evaluate("Qna.INTROS")
    assert len(intros) >= 10
    with page.expect_response("**/api/qna/admin/questions/*/show"):
        page.click("#col-disetujui [data-act=show]")
    q = backend._q(qid)
    assert q["intro"] in intros
    assert q["sfx"] in ("ding", "tada", "confetti")


def test_display_reads_intro_then_body_and_shows_votes_badge(page: Page, backend):
    backend.settings["points_mode"] = "upvote"
    qid = backend.add("Apa itu panggilan?", "disetujui", votes=3)
    page.add_init_script(RECORD_SPEECH)
    page.goto(f"{BASE}/tanya/display")
    page.click("#start")
    expect(page.locator("#conn")).to_have_class(re.compile(r"\bon\b"))
    backend.act(qid, "show", intro="Eh, ada pertanyaan nih!", sfx="confetti")
    expect(page.locator("#points")).to_have_text("Eh, ada pertanyaan nih!", timeout=10000)
    expect(page.locator("#votes")).to_have_text("▲ 3 teman ikut penasaran")
    page.wait_for_function("window.__spoken.length >= 2", timeout=10000)
    # Dibacakan terpisah supaya ada jeda: pesan pembuka dulu, baru isi pertanyaan.
    assert page.evaluate("window.__spoken.slice(0, 2)") == ["Eh, ada pertanyaan nih!", "Apa itu panggilan?"]


def test_display_hides_votes_badge_in_hiasan_mode(page: Page, backend):
    qid = backend.add("Tanpa lencana", "disetujui")
    page.goto(f"{BASE}/tanya/display")
    page.click("#start")
    expect(page.locator("#conn")).to_have_class(re.compile(r"\bon\b"))
    backend.act(qid, "show", sfx="tada")
    expect(page.locator("#qbody")).to_have_text("Tanpa lencana", timeout=10000)
    expect(page.locator("#votes")).to_be_hidden()
