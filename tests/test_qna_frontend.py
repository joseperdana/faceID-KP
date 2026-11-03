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

    def act(self, qid, action):
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
            self.settings.update(hidden=False, show_nonce=self.settings["show_nonce"] + 1)
        elif action == "done":
            q["status"] = "selesai"
            self.settings["show_nonce"] += 1

    def screen(self, action):
        self.settings.update(hidden=(action == "hide"), show_nonce=self.settings["show_nonce"] + 1)

    def display(self):
        q = next((q for q in self.questions if q["status"] == "tampil"), None)
        base = {"nonce": self.settings["show_nonce"], "tts_engine": "browser"}
        if not q or self.settings["hidden"]:
            return {**base, "question": None}
        return {**base, "question": {"id": q["id"], "body": q["body"], "points_text": "Seseorang memberikan 50 poin!"}}

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
                       "questions": [{k: v for k, v in q.items() if k != "voters"} for q in self.questions]})
        m = re.fullmatch(r"/api/qna/admin/questions/([^/]+)/(\w+)", path)
        if m:
            self.act(m.group(1), m.group(2))
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
