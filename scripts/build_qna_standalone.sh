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

case "$KEY" in
  sb_secret_*) echo "Itu secret key. Pakai publishable key (sb_publishable_...)." >&2; exit 1 ;;
esac

# rm -rf hanya untuk folder kosong atau hasil build sebelumnya.
if [ -e "$OUT" ] && [ -n "$(ls -A "$OUT")" ] && [ ! -f "$OUT/static/qna/qna-api-supabase.js" ]; then
  echo "Folder $OUT berisi file lain; pilih folder kosong." >&2
  exit 1
fi

SRC="$(cd "$(dirname "$0")/.." && pwd)/frontend/qna"
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

echo "Siap: $OUT — unggah ke https://app.netlify.com/drop"
