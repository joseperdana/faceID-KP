"""qna_service hanya penerjemah: nama parameter RPC dan pesan error DB → HTTP.

Aturan bisnisnya sendiri diuji di scripts/qna_selftest.sql.
"""
import pytest
from postgrest.exceptions import APIError

from services import qna_service
from services.qna_service import QnaError


class FakeRpc:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error
        self.calls = []

    def rpc(self, fn, params):
        self.calls.append((fn, params))
        return self

    def execute(self):
        if self.error:
            raise self.error
        return self


def _db_error(message):
    return APIError({"message": message, "code": "P0001", "hint": None, "details": None})


@pytest.fixture
def fake(monkeypatch):
    rpc = FakeRpc(data={})
    monkeypatch.setattr(qna_service, "supabase", rpc)
    return rpc


def test_submit_sends_named_params(fake):
    fake.data = {"id": "abc"}
    assert qna_service.submit("Halo semua", "dev-1") == {"id": "abc"}
    assert fake.calls == [("qna_submit", {"p_body": "Halo semua", "p_device": "dev-1"})]


def test_vote_and_public_list_params(fake):
    fake.data = []
    assert qna_service.public_list("dev-1") == []
    fake.data = {"votes": 1, "voted": True}
    qna_service.vote("q-1", "dev-1", True)
    assert fake.calls == [
        ("qna_public_list", {"p_device": "dev-1"}),
        ("qna_vote", {"p_question": "q-1", "p_device": "dev-1", "p_on": True}),
    ]


def test_admin_calls_send_null_pin_so_db_checks_service_role(fake):
    qna_service.admin_list()
    qna_service.admin_act("q-1", "show")
    qna_service.admin_screen("hide")
    qna_service.admin_settings(session_open=True)
    assert fake.calls == [
        ("qna_admin_list", {"p_pin": None}),
        ("qna_admin_act", {"p_pin": None, "p_id": "q-1", "p_action": "show", "p_intro": None, "p_sfx": None}),
        ("qna_admin_screen", {"p_pin": None, "p_action": "hide"}),
        ("qna_admin_settings", {"p_pin": None, "p_session_open": True,
                                "p_points_mode": None, "p_tts_engine": None}),
    ]


def test_cooldown_becomes_429_with_retry_after(fake):
    fake.error = _db_error("cooldown:12")
    with pytest.raises(QnaError) as exc:
        qna_service.submit("Halo semua", "dev-1")
    assert (exc.value.code, exc.value.status, exc.value.retry_after) == ("cooldown", 429, 12)


@pytest.mark.parametrize("message, status", [
    ("session_closed", 409), ("invalid_body", 400), ("invalid_device", 400),
    ("not_votable", 409), ("not_found", 404), ("invalid_transition", 409),
    ("invalid_action", 400), ("mode_locked", 409), ("nothing_showing", 409),
    ("forbidden", 403), ("invalid_intro", 400), ("invalid_sfx", 400),
])
def test_known_db_errors_map_to_http_status(fake, message, status):
    fake.error = _db_error(message)
    with pytest.raises(QnaError) as exc:
        qna_service.display()
    assert exc.value.code == message
    assert exc.value.status == status
    assert exc.value.message  # pesan Bahasa Indonesia untuk pengguna


def test_unknown_db_error_is_not_swallowed(fake):
    fake.error = _db_error('relation "qna_settings" does not exist')
    with pytest.raises(APIError):
        qna_service.get_state()


def test_unexpected_shapes_fall_back_to_safe_defaults(fake):
    # FakeSupabase di test_no_blocking_io.py mengembalikan [] untuk semua RPC.
    fake.data = []
    assert qna_service.get_state() == {"session_open": False, "points_mode": "hiasan"}
    assert qna_service.display() == {"nonce": 0, "question": None, "tts_engine": "browser"}
    assert qna_service.admin_list() == {"settings": {}, "questions": []}
    fake.data = None
    assert qna_service.public_list("dev-1") == []


def test_qna_flag_exists_and_defaults_off():
    from core import flags
    assert "qna" in flags.FLAGS
    assert flags._defaults()["qna"] is False


def test_show_passes_intro_and_sfx(fake):
    qna_service.admin_act("q-1", "show", intro="Eh, ada pertanyaan nih!", sfx="tada")
    assert fake.calls == [("qna_admin_act", {
        "p_pin": None, "p_id": "q-1", "p_action": "show",
        "p_intro": "Eh, ada pertanyaan nih!", "p_sfx": "tada",
    })]
