"""Face matching thresholds, ambiguity rejection, and frame averaging.

The recognition engine had no tests at all. The three behaviours asserted here
each correspond to a way the system silently recorded attendance under the wrong
person's name.
"""

import io
from unittest.mock import patch

import numpy as np
import pytest

from core import config
from face_service import average_embeddings
from services.db_service import DBService

JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 200


# --- threshold configuration ---------------------------------------------


def test_duplicate_threshold_is_looser_than_match_threshold():
    """The dead zone that logged attendance under the wrong name.

    Registration used 0.5 while recognition used 0.42, so a face similar at 0.45
    passed the duplicate check (0.45 < 0.5, "a different person") and was then
    matched to that existing member at check-in (0.45 >= 0.42).
    """
    assert (
        config.FACE_DUPLICATE_THRESHOLD <= config.FACE_MATCH_THRESHOLD
    ), "Duplicate detection must catch every face that recognition could later match"


def test_config_rejects_an_inverted_threshold_pair():
    from core.config import ConfigError

    with (
        patch.object(config, "FACE_DUPLICATE_THRESHOLD", 0.5),
        patch.object(config, "FACE_MATCH_THRESHOLD", 0.42),
    ):
        with pytest.raises(ConfigError, match="zona mati"):
            config.validate()


# --- embedding averaging --------------------------------------------------


def test_average_is_not_dominated_by_the_brightest_frame():
    """A plain mean weights by magnitude, which tracks brightness.

    Two frames point one way, one frame points elsewhere but is three times
    longer. np.mean follows the long vector; the direction-based average follows
    the majority, which is the person's actual identity.
    """
    a = [1.0, 0.0, 0.0]
    b = [0.96, 0.28, 0.0]
    bright_outlier = [0.0, 30.0, 0.0]

    naive = np.mean([a, b, bright_outlier], axis=0)
    naive_unit = naive / np.linalg.norm(naive)

    result = np.asarray(average_embeddings([a, b, bright_outlier]))
    result_unit = result / np.linalg.norm(result)

    # The naive mean is dragged onto the outlier's axis; ours stays near a/b.
    assert naive_unit[1] > 0.9
    assert result_unit[0] > 0.7


def test_average_preserves_single_frame_scale():
    """Output magnitude stays comparable to embeddings already in the database."""
    vectors = [[20.0, 0.0, 0.0], [0.0, 22.0, 0.0], [0.0, 0.0, 21.0]]
    result = np.linalg.norm(average_embeddings(vectors))
    assert 20.0 <= result <= 22.0


def test_average_ignores_zero_vectors():
    result = average_embeddings([[3.0, 4.0, 0.0], [0.0, 0.0, 0.0]])
    assert np.linalg.norm(result) == pytest.approx(5.0)


def test_average_rejects_empty_input():
    with pytest.raises(ValueError):
        average_embeddings([])


def test_average_rejects_frames_that_cancel_out():
    with pytest.raises(ValueError, match="terlalu berbeda"):
        average_embeddings([[1.0, 0.0], [-1.0, 0.0]])


# --- recognition endpoint -------------------------------------------------


def _patch_embedding(vector):
    return patch("face_service.FaceService.get_embedding", return_value=vector)


def test_ambiguous_match_is_refused_rather_than_guessed(client):
    """Two candidates within the margin means siblings, not a decision to make."""
    candidates = [
        {"id": 1, "full_name": "Andre", "similarity": 0.62},
        {"id": 2, "full_name": "Andrea", "similarity": 0.60},
    ]
    with (
        _patch_embedding([0.1] * 512),
        patch.object(DBService, "match_faces", return_value=candidates),
    ):
        response = client.post(
            "/api/recognize",
            files={"file": ("f.jpg", io.BytesIO(JPEG_HEADER), "image/jpeg")},
            data={"lat": "-7.979261", "lng": "112.625760"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ambiguous"


def test_clear_winner_is_accepted(client):
    candidates = [
        {"id": 1, "full_name": "Andre", "similarity": 0.81},
        {"id": 2, "full_name": "Andrea", "similarity": 0.44},
    ]
    with (
        _patch_embedding([0.1] * 512),
        patch.object(DBService, "match_faces", return_value=candidates),
        patch.object(DBService, "check_user_log_today", return_value=[]),
        patch.object(
            DBService, "get_attendance_summary", return_value={"total": 1, "last_seen": None}
        ),
        patch.object(DBService, "insert_log"),
    ):
        response = client.post(
            "/api/recognize",
            files={"file": ("f.jpg", io.BytesIO(JPEG_HEADER), "image/jpeg")},
            data={"lat": "-7.979261", "lng": "112.625760"},
        )

    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["name"] == "Andre"


def test_no_face_in_frame_returns_400_not_500(client):
    """The bug that sent registered members back to the registration form.

    `raise HTTPException(400)` sat inside a `try` whose `except Exception`
    caught it and re-raised as 500; the kiosk rendered every non-403 as
    "wajah belum terdaftar" and offered a "Daftar Anggota Baru" button.
    """
    with _patch_embedding(None):
        response = client.post(
            "/api/recognize",
            files={"file": ("f.jpg", io.BytesIO(JPEG_HEADER), "image/jpeg")},
            data={"lat": "-7.979261", "lng": "112.625760"},
        )

    assert response.status_code == 400
    assert "tidak terdeteksi" in response.json()["detail"].lower()


def test_model_unavailable_returns_503(client):
    from face_service import FaceServiceUnavailable

    with patch(
        "face_service.FaceService.get_embedding",
        side_effect=FaceServiceUnavailable("model missing"),
    ):
        response = client.post(
            "/api/recognize",
            files={"file": ("f.jpg", io.BytesIO(JPEG_HEADER), "image/jpeg")},
            data={"lat": "-7.979261", "lng": "112.625760"},
        )

    assert response.status_code == 503
    assert "Manual" in response.json()["detail"]


def test_unknown_face_is_reported_as_unknown(client):
    with _patch_embedding([0.1] * 512), patch.object(DBService, "match_faces", return_value=[]):
        response = client.post(
            "/api/recognize",
            files={"file": ("f.jpg", io.BytesIO(JPEG_HEADER), "image/jpeg")},
            data={"lat": "-7.979261", "lng": "112.625760"},
        )

    assert response.json()["status"] == "unknown"
