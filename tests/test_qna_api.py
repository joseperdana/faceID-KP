import asyncio

import pytest
from fastapi.testclient import TestClient

from core import flags, qna_bus
from core.security import COOKIE_NAME, create_access_token
from main import app
from routers import qna as qna_router
from services import tts_service
from services.qna_service import QnaError

client = TestClient(app)
DEVICE = "11111111-1111-4111-8111-111111111111"
QID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def qna_on(monkeypatch):
    monkeypatch.setattr(flags, "_refresh", lambda: {**flags._defaults(), "qna": True})


@pytest.fixture
def published(monkeypatch):
    kinds = []
    monkeypatch.setattr(qna_router.qna_bus, "publish", kinds.append)
    return kinds


def admin_client() -> TestClient:
    c = TestClient(app)
    c.cookies.set(COOKIE_NAME, create_access_token({"sub": "admin"}))
    return c


def test_public_api_is_404_while_flag_off():
    assert client.get("/api/qna/state").status_code == 404
    res = client.post("/api/qna/questions", json={"body": "Halo semua", "device_id": DEVICE})
    assert res.status_code == 404


def test_state(qna_on, monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "get_state",
                        lambda: {"session_open": True, "points_mode": "upvote"})
    res = client.get("/api/qna/state")
    assert res.json() == {"status": "success", "data": {"session_open": True, "points_mode": "upvote"}}


def test_submit_calls_service_and_announces(qna_on, published, monkeypatch):
    seen = []
    monkeypatch.setattr(qna_router.qna_service, "submit",
                        lambda body, dev: seen.append((body, dev)) or {"id": QID})
    res = client.post("/api/qna/questions",
                      json={"body": "Gimana cara tahu panggilan hidup?", "device_id": DEVICE})
    assert res.status_code == 200
    assert res.json()["data"] == {"id": QID}
    assert seen == [("Gimana cara tahu panggilan hidup?", DEVICE)]
    assert published == ["questions"]


def test_cooldown_is_429_with_retry_after_and_no_announcement(qna_on, published, monkeypatch):
    def refuse(*_):
        raise QnaError("cooldown", retry_after=12)
    monkeypatch.setattr(qna_router.qna_service, "submit", refuse)
    res = client.post("/api/qna/questions", json={"body": "Halo semua", "device_id": DEVICE})
    assert res.status_code == 429
    assert res.json()["code"] == "cooldown"
    assert res.json()["retry_after"] == 12
    assert published == []


def test_device_id_must_be_uuid(qna_on):
    res = client.post("/api/qna/questions", json={"body": "Halo semua", "device_id": "bukan-uuid"})
    assert res.status_code == 422


def test_public_list_and_vote(qna_on, published, monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "public_list",
                        lambda dev: [{"id": QID, "body": "x", "votes": 0, "voted": False, "showing": False}])
    votes = []
    monkeypatch.setattr(qna_router.qna_service, "vote",
                        lambda qid, dev, on: votes.append((qid, dev, on)) or {"votes": 1, "voted": on})
    assert client.get("/api/qna/questions/public", params={"device_id": DEVICE}).json()["data"][0]["id"] == QID
    res = client.post(f"/api/qna/questions/{QID}/vote", json={"device_id": DEVICE, "on": True})
    assert res.json()["data"] == {"votes": 1, "voted": True}
    assert votes == [(QID, DEVICE, True)]
    assert published == ["questions"]


def test_display_is_public_even_while_flag_off(monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "display",
                        lambda: {"nonce": 3, "question": None, "tts_engine": "browser"})
    assert client.get("/api/qna/display").json()["data"]["nonce"] == 3


def test_unexpected_error_is_500_without_internal_details(qna_on, monkeypatch):
    def boom():
        raise RuntimeError("detail-internal-rahasia")
    monkeypatch.setattr(qna_router.qna_service, "get_state", boom)
    res = client.get("/api/qna/state")
    assert res.status_code == 500
    assert res.json() == {
        "status": "error", "code": "server",
        "message": "Terjadi kesalahan di server.", "retry_after": None,
    }
    assert "rahasia" not in res.text


def test_admin_routes_need_login():
    for method, url in [
        ("GET", "/api/qna/admin/questions"),
        ("POST", f"/api/qna/admin/questions/{QID}/approve"),
        ("POST", "/api/qna/admin/screen/hide"),
        ("PATCH", "/api/qna/admin/settings"),
        ("GET", "/api/qna/admin/stream"),
    ]:
        assert client.request(method, url, json={}).status_code == 401, url


def test_show_announces_questions_and_display(published, monkeypatch):
    calls = []
    monkeypatch.setattr(qna_router.qna_service, "admin_act",
                        lambda qid, action: calls.append((qid, action)) or {"id": qid, "action": action})
    res = admin_client().post(f"/api/qna/admin/questions/{QID}/show")
    assert res.status_code == 200
    assert calls == [(QID, "show")]
    assert published == ["questions", "display"]


def test_approve_does_not_touch_display(published, monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "admin_act", lambda qid, action: {"id": qid, "action": action})
    admin_client().post(f"/api/qna/admin/questions/{QID}/approve")
    assert published == ["questions"]


def test_unknown_action_is_400_and_never_reaches_db(published, monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "admin_act",
                        lambda *_: pytest.fail("aksi tak dikenal tidak boleh sampai ke DB"))
    res = admin_client().post(f"/api/qna/admin/questions/{QID}/hapus")
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_action"
    assert published == []


def test_screen_replay_announces_display(published, monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "admin_screen", lambda action: {"show_nonce": 5})
    assert admin_client().post("/api/qna/admin/screen/replay").status_code == 200
    assert published == ["display"]


def test_settings_patch_sends_only_given_fields(published, monkeypatch):
    seen = []
    monkeypatch.setattr(qna_router.qna_service, "admin_settings", lambda **kw: seen.append(kw) or {})
    res = admin_client().patch("/api/qna/admin/settings", json={"session_open": True})
    assert res.status_code == 200
    assert seen == [{"session_open": True, "points_mode": None, "tts_engine": None}]
    assert published == ["settings", "display"]


def test_settings_rejects_unknown_mode():
    res = admin_client().patch("/api/qna/admin/settings", json={"points_mode": "lelang"})
    assert res.status_code == 422


def test_stream_says_hello_with_sse_headers_and_closes():
    res = admin_client().get("/api/qna/admin/stream", params={"max_seconds": 0})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert res.headers["x-accel-buffering"] == "no"
    assert "event: hello" in res.text


def test_event_stream_forwards_published_kind_and_pings():
    async def scenario():
        async def connected():
            return False
        gen = qna_router.event_stream(connected, max_seconds=5, ping_seconds=0.2)
        hello = await gen.__anext__()
        await asyncio.to_thread(qna_bus.publish, "display")
        changed = await asyncio.wait_for(gen.__anext__(), timeout=1)
        ping = await asyncio.wait_for(gen.__anext__(), timeout=1)
        await gen.aclose()
        return hello, changed, ping

    hello, changed, ping = asyncio.run(scenario())
    assert hello.startswith("retry: 2000\nevent: hello")
    assert changed == 'event: changed\ndata: {"kind": "display"}\n\n'
    assert ping == ": ping\n\n"


def test_tts_returns_mp3(monkeypatch):
    monkeypatch.setattr(qna_router.tts_service, "synthesize", lambda text: b"ID3-mp3")
    res = admin_client().post("/api/qna/admin/tts", json={"text": "Seseorang bertanya!"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.content == b"ID3-mp3"


def test_tts_unavailable_is_503_without_leaking_details(monkeypatch):
    def fail(text):
        raise tts_service.TtsUnavailable("detail-internal-rahasia")
    monkeypatch.setattr(qna_router.tts_service, "synthesize", fail)
    res = admin_client().post("/api/qna/admin/tts", json={"text": "Halo"})
    assert res.status_code == 503
    assert res.json() == {
        "status": "error", "code": "tts_unavailable",
        "message": "Suara cloud tidak tersedia.", "retry_after": None,
    }
    assert "rahasia" not in res.text


def test_tts_needs_login():
    assert client.post("/api/qna/admin/tts", json={"text": "Halo"}).status_code == 401
