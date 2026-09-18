import pytest
from dotenv import load_dotenv
load_dotenv()


@pytest.fixture(autouse=True)
def pin_feature_flags(monkeypatch):
    """Kunci saklar fitur ke nilai bawaan selama pengujian.

    Dua alasan, keduanya ditemukan saat tes gagal:

    1. Nilai saklar di-cache 30 detik di memori proses, sehingga nilai dari tes
       sebelumnya terbawa ke tes berikutnya di dalam satu sesi pytest.
    2. Tanpa penguncian ini, tes membaca tabel feature_flags yang sungguhan —
       artinya hasil tes berubah setiap kali ada pengurus menggeser saklar di
       dashboard. Tes tidak boleh bergantung pada konfigurasi yang hidup.

    Tes yang memang ingin menguji keadaan saklar tertentu tetap bisa menimpanya
    dengan patch sendiri.
    """
    from core import flags
    flags._cache = {}
    flags._cached_at = 0.0
    monkeypatch.setattr(flags, "_refresh", lambda: dict(flags._defaults()))
    yield
    flags._cache = {}
    flags._cached_at = 0.0

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "permissions": ["geolocation", "camera"],
        "geolocation": {"latitude": -7.979261, "longitude": 112.625760},
    }

@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "args": [
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--allow-file-access-from-files",
        ],
    }
