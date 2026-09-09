#!/usr/bin/env bash
# Download the third-party frontend libraries into frontend/vendor/.
#
# Why: the kiosk runs on a tablet in a church hall on shared wifi. When a CDN is
# unreachable the pages lose all styling, and MediaPipe pulls a ~3 MB wasm blob
# at runtime, so face detection simply never starts. Serving these from our own
# origin removes that dependency and also removes the need for CSP to allow
# third-party script hosts.
#
#   bash scripts/vendor_assets.sh
#
# Then set window.KP_VENDOR_BASE = '/static/vendor/mediapipe/' in index.html and
# register.html, and swap the CDN <script> tags for the local copies.
set -euo pipefail

VENDOR="$(cd "$(dirname "$0")/.." && pwd)/frontend/vendor"
MP_VERSION="0.4.1646425229"
CU_VERSION="0.3.1675466862"
SWAL_VERSION="11.14.5"
CHART_VERSION="4.4.7"

mkdir -p "$VENDOR/mediapipe" "$VENDOR/lib"

fetch() {
  local url="$1" dest="$2"
  echo "  -> ${dest##*/}"
  curl -fsSL --retry 3 --retry-delay 2 "$url" -o "$dest"
}

echo "MediaPipe face detection ($MP_VERSION)"
for file in \
  face_detection.js \
  face_detection_solution_packed_assets_loader.js \
  face_detection_solution_simd_wasm_bin.js \
  face_detection_solution_simd_wasm_bin.wasm \
  face_detection_solution_packed_assets.data \
  face_detection_short_range.tflite \
  face_detection_full_range.tflite
do
  fetch "https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@${MP_VERSION}/${file}" \
        "$VENDOR/mediapipe/$file" || echo "     (optional asset missing, continuing)"
done

echo "MediaPipe camera utils ($CU_VERSION)"
fetch "https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@${CU_VERSION}/camera_utils.js" \
      "$VENDOR/lib/camera_utils.js"

echo "SweetAlert2 ($SWAL_VERSION)"
fetch "https://cdn.jsdelivr.net/npm/sweetalert2@${SWAL_VERSION}/dist/sweetalert2.all.min.js" \
      "$VENDOR/lib/sweetalert2.all.min.js"

echo "Chart.js ($CHART_VERSION)"
fetch "https://cdn.jsdelivr.net/npm/chart.js@${CHART_VERSION}/dist/chart.umd.min.js" \
      "$VENDOR/lib/chart.umd.min.js"

echo
echo "Done. Files in $VENDOR"
echo
echo "Next: in frontend/index.html and frontend/register.html set"
echo "  <script>window.KP_VENDOR_BASE = '/static/vendor/mediapipe/';</script>"
echo "and point the <script src> tags at /static/vendor/... instead of cdn.jsdelivr.net."
echo
echo "Tailwind still needs a real build to be fully offline:"
echo "  npx tailwindcss -i frontend/src/app.css -o frontend/vendor/app.css --minify"
echo "  (with content: ['./frontend/**/*.{html,js}'] so classes built in JS template"
echo "   literals are not purged)"
