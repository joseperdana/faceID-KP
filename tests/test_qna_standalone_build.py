import subprocess  # noqa: S404 — menjalankan skrip build milik repo sendiri
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_qna_standalone.sh"


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


def test_build_refuses_to_wipe_unrelated_folder(tmp_path):
    (tmp_path / "penting.txt").write_text("jangan dihapus")
    res = run(str(tmp_path), "https://abc.supabase.co", "sb_publishable_xyz")
    assert res.returncode != 0
    assert (tmp_path / "penting.txt").exists()
