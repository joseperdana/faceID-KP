import sentry_sdk

import main  # noqa: F401  (import memicu sentry_sdk.init di main.py)


def test_sentry_tidak_merekam_variabel_lokal():
    """Sentry merekam variabel lokal tiap frame; frame httpx/postgrest memuat
    header berisi kunci Supabase, dan EventScrubber bawaan tidak menyaring
    header. Opsi ini harus tetap mati. Client dibuat walau DSN kosong, jadi
    options selalu ada di test."""
    assert sentry_sdk.get_client().options["include_local_variables"] is False
