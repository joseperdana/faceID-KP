"""Google Cloud Text-to-Speech untuk alert tanya jawab.

Kunci API hanya hidup di server (.env) dan dikirim lewat header, bukan
query string: pesan error httpx menyertakan URL lengkap, dan URL itu bisa
sampai ke log dan Sentry.
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
    key = os.getenv("GOOGLE_TTS_API_KEY")
    if not key:
        raise TtsUnavailable("GOOGLE_TTS_API_KEY belum diisi")
    body = {
        "input": {"text": text},
        "voice": {"languageCode": "id-ID", "name": os.getenv("GOOGLE_TTS_VOICE", "id-ID-Wavenet-A")},
        "audioConfig": {"audioEncoding": "MP3"},
    }
    try:
        res = httpx.post(GOOGLE_TTS_URL, headers={"X-Goog-Api-Key": key}, json=body, timeout=TIMEOUT_S)
        res.raise_for_status()
        return base64.b64decode(res.json()["audioContent"])
    except (httpx.HTTPError, KeyError, ValueError) as e:
        capture_error(e, where="qna.tts")
        raise TtsUnavailable("TTS cloud gagal") from e
