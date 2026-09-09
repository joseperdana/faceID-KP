"""Photobooth upload validation, id entropy, and retention."""

import base64
import time
from unittest.mock import patch

import pytest

from core import config
from routers import photobooth

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 500
GIF = b"GIF89a" + b"\x00" * 500


def _b64(data: bytes, prefix="data:image/jpeg;base64,") -> str:
    return prefix + base64.b64encode(data).decode()


def test_upload_accepts_a_valid_strip(client, tmp_path):
    with patch.object(photobooth, "UPLOAD_DIR", tmp_path):
        response = client.post("/api/photobooth/upload", json={"image": _b64(JPEG)})

    assert response.status_code == 200
    body = response.json()
    # A full uuid4 hex, not the previous 8 characters (32 bits), which were
    # cheap to enumerate and exposed other people's photos.
    assert len(body["photo_id"]) == 32
    assert (tmp_path / f"{body['photo_id']}.jpg").exists()


def test_upload_rejects_non_jpeg_payload(client, tmp_path):
    with patch.object(photobooth, "UPLOAD_DIR", tmp_path):
        response = client.post(
            "/api/photobooth/upload", json={"image": _b64(b"not an image at all")}
        )
    assert response.status_code == 415


def test_upload_rejects_invalid_base64(client, tmp_path):
    with patch.object(photobooth, "UPLOAD_DIR", tmp_path):
        response = client.post("/api/photobooth/upload", json={"image": "!!!not base64!!!"})
    assert response.status_code == 400


def test_oversized_payload_is_rejected_before_decoding(client, tmp_path):
    """The size check has to run on the encoded string.

    Decoding first meant the full payload was allocated in memory and only then
    declared too large — backwards for a denial-of-service guard.
    """
    huge = "A" * (int(config.PHOTOBOOTH_MAX_BYTES * 4 / 3) + 1000)
    with (
        patch.object(photobooth, "UPLOAD_DIR", tmp_path),
        patch.object(base64, "b64decode", side_effect=AssertionError("must not decode")),
    ):
        response = client.post(
            "/api/photobooth/upload", json={"image": "data:image/jpeg;base64," + huge}
        )
    assert response.status_code == 413


def test_gif_is_size_checked_too(client, tmp_path):
    """gif_image had no size limit at all."""
    huge = "A" * (int(config.PHOTOBOOTH_MAX_BYTES * 4 / 3) + 1000)
    with patch.object(photobooth, "UPLOAD_DIR", tmp_path):
        response = client.post(
            "/api/photobooth/upload",
            json={"image": _b64(JPEG), "gif_image": "data:image/gif;base64," + huge},
        )
    assert response.status_code == 413


def test_valid_gif_is_stored(client, tmp_path):
    with patch.object(photobooth, "UPLOAD_DIR", tmp_path):
        response = client.post(
            "/api/photobooth/upload",
            json={"image": _b64(JPEG), "gif_image": _b64(GIF, "data:image/gif;base64,")},
        )
    body = response.json()
    assert body["gif_download_url"].endswith(".gif")
    assert (tmp_path / f"{body['photo_id']}.gif").exists()


@pytest.mark.parametrize(
    "photo_id",
    ["../../etc/passwd", "abc", "", "x" * 32, "0123456789abcdef0123456789abcdeF"],
)
def test_view_rejects_ids_that_are_not_uuid_hex(client, photo_id):
    response = client.get(f"/p/{photo_id}", follow_redirects=False)
    assert response.status_code in (404, 307)


def test_view_returns_404_for_a_well_formed_but_missing_id(client, tmp_path):
    with patch.object(photobooth, "UPLOAD_DIR", tmp_path):
        response = client.get("/p/" + "a" * 32)
    assert response.status_code == 404
    assert "Tidak Ditemukan" in response.text


def test_view_renders_the_photo_page(client, tmp_path):
    photo_id = "b" * 32
    (tmp_path / f"{photo_id}.jpg").write_bytes(JPEG)
    with patch.object(photobooth, "UPLOAD_DIR", tmp_path):
        response = client.get(f"/p/{photo_id}")

    assert response.status_code == 200
    assert photo_id in response.text
    # Pinch-zoom must not be blocked (WCAG 1.4.4) on a page only ever opened on
    # a phone.
    assert "user-scalable=no" not in response.text
    # No unfilled placeholders left behind.
    assert "{{" not in response.text


def test_prune_removes_expired_files_and_keeps_recent_ones(tmp_path):
    old = tmp_path / ("c" * 32 + ".jpg")
    fresh = tmp_path / ("d" * 32 + ".jpg")
    keep = tmp_path / ".gitkeep"
    for path in (old, fresh, keep):
        path.write_bytes(JPEG)

    long_ago = time.time() - (30 * 86400)
    import os

    os.utime(old, (long_ago, long_ago))

    with patch.object(photobooth, "UPLOAD_DIR", tmp_path):
        removed = photobooth.prune_old_photos(retention_days=14)

    assert removed == 1
    assert not old.exists()
    assert fresh.exists()
    assert keep.exists()


def test_prune_is_a_noop_when_retention_is_disabled(tmp_path):
    with patch.object(photobooth, "UPLOAD_DIR", tmp_path):
        assert photobooth.prune_old_photos(retention_days=0) == 0
