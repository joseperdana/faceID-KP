import base64

import httpx
import pytest

from services import tts_service


def test_missing_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("GOOGLE_TTS_API_KEY", raising=False)
    with pytest.raises(tts_service.TtsUnavailable):
        tts_service.synthesize("Halo")


def test_success_decodes_audio_and_keeps_key_out_of_url(monkeypatch):
    monkeypatch.setenv("GOOGLE_TTS_API_KEY", "kunci-uji")
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json, timeout=timeout)
        return httpx.Response(200, json={"audioContent": base64.b64encode(b"mp3").decode()},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(tts_service.httpx, "post", fake_post)
    assert tts_service.synthesize("Halo") == b"mp3"
    assert "kunci-uji" not in seen["url"]
    assert seen["headers"]["X-Goog-Api-Key"] == "kunci-uji"
    assert seen["json"]["voice"]["languageCode"] == "id-ID"
    assert seen["json"]["input"]["text"] == "Halo"
    assert seen["timeout"] == tts_service.TIMEOUT_S


@pytest.mark.parametrize("failure", [
    lambda url, **_: httpx.Response(403, json={}, request=httpx.Request("POST", url)),
    lambda url, **_: (_ for _ in ()).throw(httpx.ReadTimeout("lambat")),
    lambda url, **_: httpx.Response(200, json={}, request=httpx.Request("POST", url)),
])
def test_any_failure_is_unavailable(monkeypatch, failure):
    monkeypatch.setenv("GOOGLE_TTS_API_KEY", "kunci-uji")
    monkeypatch.setattr(tts_service.httpx, "post", failure)
    with pytest.raises(tts_service.TtsUnavailable):
        tts_service.synthesize("Halo")
