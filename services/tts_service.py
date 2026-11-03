"""Google Cloud Text-to-Speech untuk alert tanya jawab.

Kunci API hanya hidup di server (.env) dan dikirim lewat header, bukan
query string. Jangan sampai kunci ikut terekam ke log atau Sentry, lewat tiga
jalur: URL di pesan error httpx, variabel lokal setiap frame di traceback
(Sentry merekamnya karena include_local_variables aktif), dan header request
di frame internal httpx. Karena itu error yang dilaporkan dibuat ulang tanpa
traceback, hanya memuat nama jenis error-nya.
"""
import base64
import os

import httpx

from core.observability import capture_error

GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
# Display pindah ke suara browser kalau lebih lama dari ini; menunggu lebih
# lama hanya membuat ruangan hening di depan videotron.
TIMEOUT_S = 4.0


class TtsUnavailable(Exception):
    pass


def synthesize(text: str) -> bytes:
    api_key = os.getenv("GOOGLE_TTS_API_KEY")
    if not api_key:
        raise TtsUnavailable("GOOGLE_TTS_API_KEY belum diisi")
    body = {
        "input": {"text": text},
        "voice": {"languageCode": "id-ID", "name": os.getenv("GOOGLE_TTS_VOICE", "id-ID-Wavenet-A")},
        "audioConfig": {"audioEncoding": "MP3"},
    }
    try:
        res = httpx.post(GOOGLE_TTS_URL, headers={"X-Goog-Api-Key": api_key}, json=body, timeout=TIMEOUT_S)
        res.raise_for_status()
        return base64.b64decode(res.json()["audioContent"])
    except Exception as e:
        # Sentry merekam variabel lokal setiap frame; traceback httpx memuat
        # header berisi kunci, jadi yang dilaporkan hanya nama jenis error-nya.
        # Exception baru ini tidak pernah di-raise, jadi tidak punya traceback.
        capture_error(TtsUnavailable(f"TTS cloud gagal: {type(e).__name__}"), where="qna.tts")
        # from None: traceback httpx tidak ikut tersambung ke error yang diteruskan.
        raise TtsUnavailable("TTS cloud gagal") from None
