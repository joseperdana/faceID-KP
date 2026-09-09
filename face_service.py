"""Face detection and embedding extraction.

Two behaviours here matter operationally.

**Lazy, non-fatal loading.** The model used to be constructed at import time, so
a failed or slow download took the whole application down with it — including
the manual-search fallback that exists precisely for when face recognition is
unavailable. Now the app always boots; if the model cannot load, recognition
returns a clear 503 and the kiosk falls back to manual search.

**Correct multi-frame averaging.** Registration averages several frames.
InsightFace returns un-normalised vectors whose magnitude varies with lighting,
so a plain mean lets the brightest frame dominate the result. We average the
directions and restore a representative magnitude instead.
"""

import logging
import threading

import numpy as np

from core import config

logger = logging.getLogger(__name__)


class FaceServiceUnavailable(RuntimeError):
    """The recognition model could not be loaded."""


class FaceService:
    def __init__(self) -> None:
        self._app = None
        self._load_error: str | None = None
        self._lock = threading.Lock()

    # --- model lifecycle -------------------------------------------------

    def _ensure_loaded(self):
        if self._app is not None:
            return self._app
        with self._lock:
            if self._app is not None:
                return self._app
            if self._load_error is not None:
                raise FaceServiceUnavailable(self._load_error)
            try:
                from insightface.app import FaceAnalysis

                logger.info(
                    "Loading face model %s (det_size=%d)",
                    config.FACE_MODEL_NAME,
                    config.FACE_DET_SIZE,
                )
                app = FaceAnalysis(
                    name=config.FACE_MODEL_NAME,
                    providers=["CPUExecutionProvider"],
                    # Landmark (1k3d68, ~143 MB) and genderage are never read by
                    # this application but were being loaded and run on every
                    # call. Dropping them cuts both memory and latency.
                    allowed_modules=["detection", "recognition"],
                )
                # ctx_id=-1 selects CPU explicitly; the provider list already
                # rules out GPU, and the previous ctx_id=0 was misleading.
                app.prepare(ctx_id=-1, det_size=(config.FACE_DET_SIZE, config.FACE_DET_SIZE))
                self._app = app
                logger.info("Face model ready.")
                return self._app
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                self._load_error = str(exc)
                logger.exception("Face model failed to load")
                raise FaceServiceUnavailable(self._load_error) from exc

    def warm_up(self) -> bool:
        """Load the model ahead of the first request. Never raises."""
        try:
            self._ensure_loaded()
            return True
        except FaceServiceUnavailable:
            return False

    @property
    def is_available(self) -> bool:
        return self._app is not None or self._load_error is None

    # --- inference -------------------------------------------------------

    def get_embedding(self, image_bytes: bytes) -> list[float] | None:
        """Return the embedding of the largest face, or None if none is found.

        Raises ValueError for input that is not a decodable image, and
        FaceServiceUnavailable if the model is not loaded.
        """
        app = self._ensure_loaded()

        # Imported here rather than at module scope so this module (and the
        # tests that exercise average_embeddings) can be imported on a machine
        # without the native OpenCV wheel installed.
        import cv2

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Gambar tidak valid")

        # Guard against decompression bombs: a small file can decode into
        # hundreds of megapixels and exhaust a 2 GB VPS.
        height, width = img.shape[:2]
        if height * width > config.MAX_IMAGE_PIXELS:
            raise ValueError("Resolusi gambar terlalu besar")

        faces = app.get(img)
        if not faces:
            return None

        largest = max(
            faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        )
        vector = self._select_vector(largest)
        return vector.tolist()

    @staticmethod
    def _select_vector(face) -> np.ndarray:
        """Pick the raw or unit-length embedding according to configuration.

        Stored embeddings from earlier versions are un-normalised. Cosine
        distance is scale-invariant so mixing the two is harmless there, but a
        hand-provisioned database using inner-product distance would break, so
        normalisation stays opt-in.
        """
        if config.FACE_NORMALIZE_EMBEDDINGS and getattr(face, "normed_embedding", None) is not None:
            return np.asarray(face.normed_embedding, dtype=np.float64)
        return np.asarray(face.embedding, dtype=np.float64)


def average_embeddings(embeddings: list[list[float]]) -> list[float]:
    """Combine several frames of the same person into one embedding.

    A plain `np.mean` over un-normalised vectors is weighted by magnitude, which
    for InsightFace tracks image brightness and face size — so the single most
    brightly lit frame dominates the identity. We average the unit directions
    and rescale to the mean magnitude, which keeps the result on the same scale
    as a single-frame embedding (so it stays comparable to rows already stored).
    """
    if not embeddings:
        raise ValueError("Tidak ada embedding untuk dirata-ratakan")

    matrix = np.asarray(embeddings, dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    # A zero vector would produce NaN; drop those frames rather than poison the mean.
    usable = norms.squeeze(axis=1) > 1e-9
    if not usable.any():
        raise ValueError("Embedding tidak valid")
    matrix = matrix[usable]
    norms = norms[usable]

    directions = matrix / norms
    mean_direction = directions.mean(axis=0)
    mean_direction_norm = np.linalg.norm(mean_direction)
    if mean_direction_norm < 1e-9:
        raise ValueError("Frame wajah terlalu berbeda satu sama lain")
    unit = mean_direction / mean_direction_norm

    if config.FACE_NORMALIZE_EMBEDDINGS:
        return unit.tolist()
    return (unit * float(norms.mean())).tolist()


# Module-level handle. Constructing it is cheap now: no model is touched until
# the first call to get_embedding() or warm_up().
face_service = FaceService()
