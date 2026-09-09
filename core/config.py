"""Centralised configuration with fail-fast validation at import time.

Every environment variable the application reads is declared here exactly once,
so there is a single place to look when a deploy fails. Previously each module
read os.getenv() with its own failure behaviour (ValueError in database.py,
KeyError in core/security.py, a silent None in routers/auth.py), which meant a
misconfigured server could boot half-working and only fail at the first scan.

Validation collects *all* problems and raises once, so a fresh deploy learns
about every missing variable in a single run instead of one per restart.
"""

import os
import secrets
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised at startup when the environment is not usable."""


def _get(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _get_bool(name: str, default: bool) -> bool:
    raw = _get(name)
    if raw is None:
        return default
    return raw.lower() in ("true", "1", "yes", "on")


def _get_float(name: str, default: Optional[float]) -> Optional[float]:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"{name} harus berupa angka, dapat: {raw!r}")


def _get_int(name: str, default: int) -> int:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} harus berupa bilangan bulat, dapat: {raw!r}")


# --- Database -------------------------------------------------------------
SUPABASE_URL = _get("SUPABASE_URL")
SUPABASE_KEY = _get("SUPABASE_KEY")

# --- Auth -----------------------------------------------------------------
SECRET_KEY = _get("SECRET_KEY")
# Preferred: a bcrypt hash produced by scripts/hash_password.py.
# ADMIN_PASSWORD (plaintext) is still accepted so an existing deployment keeps
# working, but it is compared in constant time and warned about at startup.
ADMIN_PASSWORD_HASH = _get("ADMIN_PASSWORD_HASH")
ADMIN_PASSWORD = _get("ADMIN_PASSWORD")

# Shared secret held by the kiosk tablet. Gates the endpoints that write or
# enumerate member data without an admin session. An admin enrols a device once
# by visiting /kiosk/enroll on it; see core/security.check_kiosk_auth.
KIOSK_TOKEN = _get("KIOSK_TOKEN")

SESSION_HOURS = _get_int("SESSION_HOURS", 8)
KIOSK_TOKEN_DAYS = _get_int("KIOSK_TOKEN_DAYS", 365)

# Set COOKIE_SECURE=false only for local http development. In production this
# must stay true so the admin session cookie never crosses the network in clear.
COOKIE_SECURE = _get_bool("COOKIE_SECURE", True)

# --- Geofence -------------------------------------------------------------
# Enforced by default. When enforcement is on, the coordinates must be supplied
# explicitly: the repository previously carried two different hardcoded pairs
# roughly 965 m apart, so no built-in default can be trusted. Verify the value
# on a map before setting it, or every member will be rejected on site.
ENABLE_GEOFENCE = _get_bool("ENABLE_GEOFENCE", True)
CHURCH_LAT = _get_float("CHURCH_LAT", None)
CHURCH_LNG = _get_float("CHURCH_LNG", None)
GEOFENCE_RADIUS_METERS = _get_float("GEOFENCE_RADIUS_METERS", 200.0)

# --- Face recognition -----------------------------------------------------
# One threshold, used consistently. The duplicate check at registration must be
# LOOSER (a lower similarity bar) than recognition, otherwise a face that is too
# similar to an existing member can pass registration and then be matched to
# that member at check-in, silently logging attendance under the wrong name.
FACE_MATCH_THRESHOLD = _get_float("FACE_MATCH_THRESHOLD", 0.42)
FACE_DUPLICATE_THRESHOLD = _get_float("FACE_DUPLICATE_THRESHOLD", 0.35)
# Minimum gap between the best and second-best candidate. Below this the match
# is ambiguous (siblings, twins) and is rejected rather than guessed.
FACE_MATCH_MARGIN = _get_float("FACE_MATCH_MARGIN", 0.05)

FACE_MODEL_NAME = _get("FACE_MODEL_NAME", "buffalo_l")
FACE_DET_SIZE = _get_int("FACE_DET_SIZE", 640)
# Normalising the query vector is only safe when match_faces() compares with
# cosine distance (scale-invariant). migrations/001_init.sql does exactly that,
# but a database provisioned by hand may not, so this stays opt-in.
FACE_NORMALIZE_EMBEDDINGS = _get_bool("FACE_NORMALIZE_EMBEDDINGS", False)

# --- Uploads --------------------------------------------------------------
MAX_IMAGE_BYTES = _get_int("MAX_IMAGE_BYTES", 5 * 1024 * 1024)
MAX_REGISTER_FILES = _get_int("MAX_REGISTER_FILES", 8)
MAX_IMAGE_PIXELS = _get_int("MAX_IMAGE_PIXELS", 12_000_000)
PHOTOBOOTH_MAX_BYTES = _get_int("PHOTOBOOTH_MAX_BYTES", 8 * 1024 * 1024)
PHOTOBOOTH_RETENTION_DAYS = _get_int("PHOTOBOOTH_RETENTION_DAYS", 14)

# --- Rate limits ----------------------------------------------------------
RATE_LIMIT_STORAGE_URI = _get("RATE_LIMIT_STORAGE_URI")  # e.g. redis://127.0.0.1:6379
RATE_LIMIT_RECOGNIZE = _get("RATE_LIMIT_RECOGNIZE", "240/minute")
RATE_LIMIT_LOGIN = _get("RATE_LIMIT_LOGIN", "5/minute")
RATE_LIMIT_SEARCH = _get("RATE_LIMIT_SEARCH", "120/minute")
RATE_LIMIT_CHECKIN = _get("RATE_LIMIT_CHECKIN", "120/minute")
RATE_LIMIT_REGISTER = _get("RATE_LIMIT_REGISTER", "10/minute")
RATE_LIMIT_PHOTOBOOTH = _get("RATE_LIMIT_PHOTOBOOTH", "10/minute")

# --- Observability --------------------------------------------------------
SENTRY_DSN = _get("SENTRY_DSN")
SENTRY_TRACES_SAMPLE_RATE = _get_float("SENTRY_TRACES_SAMPLE_RATE", 0.1)
SENTRY_PROFILES_SAMPLE_RATE = _get_float("SENTRY_PROFILES_SAMPLE_RATE", 0.0)

# --- Misc -----------------------------------------------------------------
ENVIRONMENT = _get("ENVIRONMENT", "production")
IS_PRODUCTION = ENVIRONMENT == "production"


def generate_secret(length: int = 48) -> str:
    """Convenience helper used by scripts and the deploy script."""
    return secrets.token_urlsafe(length)


def validate() -> None:
    """Check the whole environment at once and raise a single actionable error."""
    problems: List[str] = []

    if not SUPABASE_URL:
        problems.append("SUPABASE_URL belum diisi.")
    if not SUPABASE_KEY:
        problems.append("SUPABASE_KEY belum diisi.")

    if not SECRET_KEY:
        problems.append(
            "SECRET_KEY belum diisi. Buat yang baru dengan:\n"
            "      python -c \"import secrets;print(secrets.token_urlsafe(48))\""
        )
    elif len(SECRET_KEY) < 32:
        problems.append(
            f"SECRET_KEY hanya {len(SECRET_KEY)} karakter; minimal 32. "
            "Kunci pendek dapat ditebak dan memungkinkan pemalsuan token admin."
        )

    if not ADMIN_PASSWORD_HASH and not ADMIN_PASSWORD:
        problems.append(
            "ADMIN_PASSWORD_HASH belum diisi. Buat dengan:\n"
            "      python scripts/hash_password.py"
        )

    if not KIOSK_TOKEN:
        problems.append(
            "KIOSK_TOKEN belum diisi. Token ini mengunci endpoint registrasi dan "
            "absen manual agar tidak terbuka ke internet. Buat dengan:\n"
            "      python -c \"import secrets;print(secrets.token_urlsafe(32))\""
        )
    elif len(KIOSK_TOKEN) < 24:
        problems.append(f"KIOSK_TOKEN hanya {len(KIOSK_TOKEN)} karakter; minimal 24.")

    if ENABLE_GEOFENCE:
        if CHURCH_LAT is None or CHURCH_LNG is None:
            problems.append(
                "ENABLE_GEOFENCE=true tetapi CHURCH_LAT/CHURCH_LNG belum diisi.\n"
                "      Verifikasi koordinat gereja di peta lebih dulu, lalu isi keduanya.\n"
                "      Jangan menebak: koordinat yang salah menolak seluruh jemaat di lokasi."
            )
        else:
            if not (-90 <= CHURCH_LAT <= 90):
                problems.append(f"CHURCH_LAT di luar rentang valid: {CHURCH_LAT}")
            if not (-180 <= CHURCH_LNG <= 180):
                problems.append(f"CHURCH_LNG di luar rentang valid: {CHURCH_LNG}")

    if FACE_DUPLICATE_THRESHOLD > FACE_MATCH_THRESHOLD:
        problems.append(
            f"FACE_DUPLICATE_THRESHOLD ({FACE_DUPLICATE_THRESHOLD}) lebih ketat daripada "
            f"FACE_MATCH_THRESHOLD ({FACE_MATCH_THRESHOLD}). Ini membuka zona mati: wajah "
            "mirip lolos saat registrasi lalu dicocokkan ke orang lain saat absen. "
            "Ambang duplikat harus lebih rendah atau sama."
        )

    if problems:
        bullet = "\n  - ".join(problems)
        raise ConfigError(
            "Konfigurasi tidak lengkap — aplikasi tidak dijalankan.\n"
            "Salin .env.example menjadi .env lalu lengkapi:\n\n"
            f"  - {bullet}\n"
        )


def startup_summary() -> str:
    """Human-readable summary printed at boot, so misconfiguration is visible."""
    lines = [
        f"environment           : {ENVIRONMENT}",
        f"admin auth            : {'bcrypt hash' if ADMIN_PASSWORD_HASH else 'PLAINTEXT (segera migrasi ke ADMIN_PASSWORD_HASH)'}",
        f"cookie secure         : {COOKIE_SECURE}",
        f"session lifetime      : {SESSION_HOURS} jam",
        f"geofence              : {'aktif' if ENABLE_GEOFENCE else 'NONAKTIF'}",
    ]
    if ENABLE_GEOFENCE:
        lines.append(
            f"geofence center       : {CHURCH_LAT}, {CHURCH_LNG} (radius {GEOFENCE_RADIUS_METERS:.0f} m)"
        )
        lines.append(
            "                        ^ verifikasi koordinat ini di peta bila belum pernah dicek"
        )
    lines += [
        f"face match threshold  : {FACE_MATCH_THRESHOLD} (duplikat {FACE_DUPLICATE_THRESHOLD}, margin {FACE_MATCH_MARGIN})",
        f"face model            : {FACE_MODEL_NAME} @ {FACE_DET_SIZE}x{FACE_DET_SIZE}",
        f"rate limit storage    : {RATE_LIMIT_STORAGE_URI or 'in-memory (per proses — pakai Redis bila >1 worker)'}",
        f"sentry                : {'aktif' if SENTRY_DSN else 'nonaktif'} (traces {SENTRY_TRACES_SAMPLE_RATE})",
    ]
    return "\n".join(f"  {line}" for line in lines)
