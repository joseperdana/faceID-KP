import re
import subprocess  # noqa: S404 — menjalankan skrip build milik repo sendiri
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_qna_standalone.sh"
LEGACY_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.x"


def run(*args):
    return subprocess.run(["/bin/bash", str(SCRIPT), *args], capture_output=True, text=True, check=False)  # noqa: S603


def test_build_produces_static_site_pointing_to_supabase(tmp_path):
    out = tmp_path / "situs"
    res = run(str(out), "https://abc.supabase.co", "sb_publishable_xyz")
    assert res.returncode == 0, res.stderr
    for name in ("index.html", "admin.html", "display.html", "_headers",
                 "static/qna/qna-api-supabase.js", "static/qna/qna.css"):
        assert (out / name).exists(), name
    config = (out / "static/qna/config.js").read_text()
    assert 'backend: "supabase"' in config
    assert "https://abc.supabase.co" in config and "sb_publishable_xyz" in config
    assert '"/admin.html"' in config


def test_build_refuses_secret_key(tmp_path):
    res = run(str(tmp_path / "situs"), "https://abc.supabase.co", "sb_secret_bocor")
    assert res.returncode != 0
    assert not (tmp_path / "situs").exists()


def test_build_refuses_legacy_service_role_jwt(tmp_path):
    res = run(str(tmp_path / "situs"), "https://abc.supabase.co", LEGACY_JWT)
    assert res.returncode != 0
    assert "publishable" in res.stderr
    assert not (tmp_path / "situs").exists()


def test_build_refuses_url_that_could_break_out_of_js_string(tmp_path):
    res = run(str(tmp_path / "situs"), 'https://x"y.co', "sb_publishable_xyz")
    assert res.returncode != 0
    assert not (tmp_path / "situs").exists()


def test_build_strips_one_trailing_slash_from_url(tmp_path):
    out = tmp_path / "situs"
    res = run(str(out), "https://abc.supabase.co/", "sb_publishable_xyz")
    assert res.returncode == 0, res.stderr
    config = (out / "static/qna/config.js").read_text()
    assert 'supabaseUrl: "https://abc.supabase.co",' in config
    assert "https://abc.supabase.co/" not in config


def test_build_refuses_to_wipe_unrelated_folder(tmp_path):
    (tmp_path / "penting.txt").write_text("jangan dihapus")
    res = run(str(tmp_path), "https://abc.supabase.co", "sb_publishable_xyz")
    assert res.returncode != 0
    assert (tmp_path / "penting.txt").exists()


def test_build_twice_into_same_folder_succeeds(tmp_path):
    out = tmp_path / "situs"
    assert run(str(out), "https://abc.supabase.co", "sb_publishable_xyz").returncode == 0
    res = run(str(out), "https://abc.supabase.co", "sb_publishable_xyz")
    assert res.returncode == 0, res.stderr


def test_built_pages_reference_only_files_that_exist(tmp_path):
    out = tmp_path / "situs"
    assert run(str(out), "https://abc.supabase.co", "sb_publishable_xyz").returncode == 0
    for page in ("index.html", "admin.html", "display.html"):
        html = (out / page).read_text()
        for ref in re.findall(r'(?:src|href)="(/[^"]*)"', html):
            path = ref.split("?", 1)[0].split("#", 1)[0].lstrip("/") or "index.html"
            assert (out / path).is_file(), f"{page} -> {ref}"
