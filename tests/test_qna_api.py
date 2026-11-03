import pytest
from fastapi.testclient import TestClient

from core import flags
from core.security import COOKIE_NAME, create_access_token
from main import app
from routers import qna as qna_router
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
    assert "rahasia" not in res.text
