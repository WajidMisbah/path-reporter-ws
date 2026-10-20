# Path Reporter WS

Offline-first PWA for histopathology reporting from Dr. Wajid Misbahudheen's own Word templates.

* `docs/` – the app (served by GitHub Pages). Plain HTML/JS, no build step.
* `docs/templates/` – **templates bundle** (`bundle.json`) + the Basic Template `.dotx` layouts. Contains no patient data.
* `tools/gen_bundle.py` – regenerates the bundle from the case-based templates (`/workspace/casetemplates`) and the gross-description library (`/workspace/grossing`). Run it, commit, push; then press **Update templates** in the app.
* `test/e2e.py` – headless Chromium end-to-end test.

Patient data lives only in the browser's IndexedDB on the device. Use *Templates & backup → Export backup* to keep a copy.
