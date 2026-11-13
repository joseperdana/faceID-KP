#!/usr/bin/env bash
# Bangun situs statis jalur cadangan tanya jawab (spec §13).
# Halaman sama persis dengan web KP; hanya config.js yang menunjuk adapter Supabase.
#
# Pakai: scripts/build_qna_standalone.sh <folder-keluaran> <SUPABASE_URL> <PUBLISHABLE_KEY>
# Lalu seret folder keluaran ke https://app.netlify.com/drop.
# Situsnya baru berfungsi setelah scripts/qna_fallback_on.sql dijalankan.
set -euo pipefail

OUT="${1:?folder keluaran}"
URL="${2:?SUPABASE_URL}"
KEY="${3:?publishable key}"
MARKER=".qna-standalone-build"

# Semua validasi dilakukan sebelum menyentuh filesystem (rm -rf, mkdir).
# config.js ditulis ke halaman publik, jadi hanya nilai yang pasti aman yang lolos.
URL="${URL%/}" # buang satu garis miring di akhir
URL_RE='^https://[A-Za-z0-9.-]+$'
KEY_RE='^sb_publishable_[A-Za-z0-9_-]+$'

if ! [[ $KEY =~ $KEY_RE ]]; then
  echo "Pakai publishable key (sb_publishable_...). Kunci lain bisa jadi rahasia dan akan terbuka untuk semua orang." >&2
  exit 1
fi

if ! [[ $URL =~ $URL_RE ]]; then
  echo "SUPABASE_URL harus berbentuk https://<proyek>.supabase.co (tanpa path, tanpa tanda kutip)." >&2
  exit 1
fi

SRC="$(cd "$(dirname "$0")/.." && pwd)/frontend/qna"
if [ ! -d "$SRC" ]; then
  echo "Folder sumber $SRC tidak ada." >&2
  exit 1
fi

# rm -rf hanya untuk folder yang dibuat build ini sebelumnya (ada penanda).
if [ -e "$OUT" ] && [ ! -d "$OUT" ]; then
  echo "$OUT bukan folder; pilih folder kosong." >&2
  exit 1
fi
if [ -d "$OUT" ] && [ -n "$(ls -A "$OUT")" ] && [ ! -f "$OUT/$MARKER" ]; then
  echo "Folder $OUT berisi file lain; pilih folder kosong." >&2
  exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT/static/qna"
cp "$SRC"/*.js "$SRC"/*.css "$OUT/static/qna/"
cp "$SRC/tanya.html" "$OUT/index.html"
cp "$SRC/tanya-admin.html" "$OUT/admin.html"
cp "$SRC/tanya-display.html" "$OUT/display.html"

cat > "$OUT/static/qna/config.js" <<EOF
// Dibangkitkan oleh scripts/build_qna_standalone.sh — jalur cadangan tanpa web KP.
window.QNA_CONFIG = {
  backend: "supabase",
  supabaseUrl: "$URL",
  supabaseKey: "$KEY",
  pages: { jemaat: "/", admin: "/admin.html", display: "/display.html" },
};
EOF

# Sama dengan web KP: browser wajib memvalidasi ulang, jangan pakai JS lama.
cat > "$OUT/_headers" <<'EOF'
/*
  Cache-Control: no-cache, must-revalidate
EOF

# Penanda hanya ditulis setelah build berhasil; build ulang ke folder ini boleh.
: > "$OUT/$MARKER"

echo "Siap: $OUT — unggah ke https://app.netlify.com/drop"
