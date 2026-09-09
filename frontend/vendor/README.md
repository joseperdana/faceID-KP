# frontend/vendor

Third-party libraries served from our own origin.

The kiosk runs on a tablet in a church hall on shared wifi. When a CDN is
unreachable the pages lose all styling, and MediaPipe fetches a ~3 MB wasm blob
at runtime, so face detection never starts at all. Vendoring removes that
dependency on the one screen that must keep working.

Populate with:

    bash scripts/vendor_assets.sh

The contents are gitignored: they are large binaries and are reproducible from
the pinned versions in that script.
