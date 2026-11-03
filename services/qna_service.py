"""Pemanggil fungsi Postgres qna_* untuk modul tanya jawab.

Aturan bisnis (jeda per HP, transisi status, teks poin) ada di
scripts/2026-11-04_qna.sql, bukan di sini: jalur cadangan memanggil fungsi
yang sama langsung dari browser. Modul ini hanya menamai parameter dan
menerjemahkan pesan error DB menjadi status HTTP.

Semua fungsi sinkron (supabase-py) — panggil hanya dari handler `def`.
"""
from typing import Optional

from postgrest.exceptions import APIError

from database import supabase

# kode -> (status HTTP, pesan untuk pengguna)
ERRORS = {
    "session_closed": (409, "Sesi tanya jawab belum dibuka atau sudah ditutup."),
    "cooldown": (429, "Tunggu sebentar sebelum mengirim lagi."),
    "invalid_body": (400, "Pertanyaan harus 3–300 karakter."),
    "invalid_device": (400, "Perangkat tidak dikenali. Muat ulang halaman."),
    "not_votable": (409, "Pertanyaan ini sudah tidak bisa didukung."),
    "not_found": (404, "Pertanyaan tidak ditemukan."),
    "invalid_transition": (409, "Aksi ini tidak berlaku untuk status pertanyaan sekarang."),
    "invalid_action": (400, "Aksi tidak dikenal."),
    "mode_locked": (409, "Tutup sesi dulu sebelum mengganti mode poin."),
    "nothing_showing": (409, "Tidak ada pertanyaan yang sedang tampil."),
    "forbidden": (403, "Akses admin ditolak."),
}

DEFAULT_STATE = {"session_open": False, "points_mode": "hiasan"}
DEFAULT_DISPLAY = {"nonce": 0, "question": None, "tts_engine": "browser"}
DEFAULT_ADMIN_LIST = {"settings": {}, "questions": []}


class QnaError(Exception):
    """Penolakan yang dimengerti pengguna. `code` dipakai frontend."""

    def __init__(self, code: str, retry_after: Optional[int] = None):
        status, message = ERRORS[code]
        super().__init__(code)
        self.code = code
        self.status = status
        self.message = message
        self.retry_after = retry_after

    @classmethod
    def from_db_message(cls, message: str) -> Optional["QnaError"]:
        if message.startswith("cooldown:"):
            try:
                return cls("cooldown", retry_after=max(1, int(message.split(":", 1)[1])))
            except ValueError:
                return cls("cooldown", retry_after=30)
        if message in ERRORS:
            return cls(message)
        return None


def _rpc(fn: str, params: Optional[dict] = None):
    try:
        return supabase.rpc(fn, params or {}).execute().data
    except APIError as e:
        err = QnaError.from_db_message(e.message or "")
        if err is None:
            raise  # error tak dikenal = bug atau DB rusak; biarkan jadi 500 + Sentry
        raise err from None


def _obj(data, default: dict) -> dict:
    return data if isinstance(data, dict) else dict(default)


def _list(data) -> list:
    return data if isinstance(data, list) else []


def get_state() -> dict:
    return _obj(_rpc("qna_state"), DEFAULT_STATE)


def submit(body: str, device_id: str) -> dict:
    return _obj(_rpc("qna_submit", {"p_body": body, "p_device": device_id}), {})


def public_list(device_id: str) -> list:
    return _list(_rpc("qna_public_list", {"p_device": device_id}))


def vote(question_id: str, device_id: str, on: bool) -> dict:
    return _obj(_rpc("qna_vote", {"p_question": question_id, "p_device": device_id, "p_on": on}), {})


def display() -> dict:
    return _obj(_rpc("qna_display"), DEFAULT_DISPLAY)


# p_pin None: fungsi DB mengenali server dari role service_role (secret key).
def admin_list() -> dict:
    return _obj(_rpc("qna_admin_list", {"p_pin": None}), DEFAULT_ADMIN_LIST)


def admin_act(question_id: str, action: str) -> dict:
    return _obj(_rpc("qna_admin_act", {"p_pin": None, "p_id": question_id, "p_action": action}), {})


def admin_screen(action: str) -> dict:
    return _obj(_rpc("qna_admin_screen", {"p_pin": None, "p_action": action}), {})


def admin_settings(session_open: Optional[bool] = None, points_mode: Optional[str] = None,
                   tts_engine: Optional[str] = None) -> dict:
    return _obj(_rpc("qna_admin_settings", {
        "p_pin": None, "p_session_open": session_open,
        "p_points_mode": points_mode, "p_tts_engine": tts_engine,
    }), {})
