# Raw idea — Epoch 21 (Flagship end-to-end proof, all four endpoints)

From the Generation 1 roadmap (Epoch 21, items #85–87): the headline deliverable — **one
path, one region, all four endpoints.** Two layers respect the offline discipline:

- **#85 Offline all-endpoints e2e orchestration test** — one in-suite test that walks a
  single settings/request object through the digital-image, animation, print-image, and
  report code paths with injected fakes, asserting each endpoint's contract AND determinism.
- **#86 Real-data e2e harness (opt-in, outside the suite)** — a `tools/` command that takes
  one small public-domain county and produces ALL FOUR real artifacts (SVG+PNG, GIF/MP4,
  print raster, report) plus a combined provenance manifest and a double-render determinism
  check.
- **#87 E2E golden fixture** — commit the small region's expected hashes/manifest as a golden
  fixture (extends `tests/fixtures/golden/`) so the e2e path is regression-guarded.

Chosen region: **Washington / Wahkiakum** (the existing golden-fixture county in
`tests/fixtures/golden/registry.json`, and the county the Epoch 19 endpoint layer already
targets — consistency, and its real four-artifact run was deferred here from Epoch 19).

Discipline: the in-suite e2e drives `src.endpoints.dispatch_endpoint` with injected fakes; the
real artifacts need GDAL + staged NAS data, so the real harness is opt-in and its execution is
deferred to the GDAL+NAS machine (like `tools/verify_determinism.py` and the Epoch 19 real
run). Default 2D output stays byte-for-byte identical; public-domain sources only.
