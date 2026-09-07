# Implementation Report: High-resolution marketing gallery (Epoch 22, #88–90)

## Summary
A curated, rights-clean marketing gallery: a pure/offline rights-ledger core over a curated
style matrix, an opt-in high-resolution render harness (real run deferred to GDAL+NAS), a
self-contained web surface, and a render-independent golden with a regression gate. No art
feature added, no `PIPELINE_STAGES` change; the default 2D build stays byte-for-byte identical;
public-domain sources only.

## What shipped

### TG1 — Curated matrix + rights ledger (`src/gallery.py`, #88/#90)
- `GallerySelection` frozen dataclass + `GALLERY_MATRIX` (5 curated selections) spanning all four
  regions (Oregon, Washington, California, Idaho), both public-domain styles (neon-basin,
  elevation-tint), and all four endpoints (digital_image, print_image, animation, report).
- `selection_request` validates each selection through `src.endpoints.build_endpoint_request`
  (the Rights gate), so a non-sellable (PRISM-derived) or invalid selection fails fast.
- `gallery_ledger` produces a deterministic, byte-identical (`sort_keys`) provenance ledger
  (schema `hydro-art/gallery-ledger@1`): per-asset identity, rationale, `sellable` flag, and
  planned deliverables. Optional `checksums` stamps sha256 with **exact** per-asset coverage
  enforcement (missing/extra → `EndpointError`).
- Offline: imports only stdlib + `src.endpoints` + `src.fulfillment`.
- Tests: `tests/test_gallery.py` (6) — matrix spans the range; every selection valid+sellable;
  skeleton deterministic/byte-identical; checksum stamping + coverage rejection; golden match.

### TG2 — High-res render harness (`tools/render_gallery.py`, #89, non-suite)
- CLI (`--item`, `--out-dir`, `--web-variants`) dispatches each curated selection through the
  offline contract layer (`dispatch_endpoint`) using the four real renderer factories from
  `tools/render_endpoint._renderers`. Adds no render recipe of its own.
- Stamps a provenance rights ledger with per-file sha256s and, with `--web-variants`, emits
  web-optimized derivatives (svg via `SvgoOptimizer`, rasters downscaled via Pillow), degrading
  gracefully when optional tools are absent.
- Lives OUTSIDE the offline suite (needs GDAL + staged NAS data); never imported by `src/` or
  `tests/`. Compiles, imports clean, runs `--help`. Real render deferred to the GDAL+NAS machine.
- Exit codes: `EndpointError` → 1, acquisition/render failure → 2.

### TG3 — Web gallery surface (`web/gallery.html`, #90)
- Self-contained page (no build step, `file://`-safe): embedded sample ledger (the real
  `gallery_ledger()` skeleton) with an optional `?ledger=<url>` fetch over http(s).
- Responsive card grid: region · county, style/endpoint tags, rationale, sellable badge,
  attribution + schema line, and per-deliverable filename/dimensions.
- All DOM access inside function bodies; structural sanity checked (tag balance + JSON parse +
  filename/endpoint match against the real `src.gallery.gallery_ledger()` skeleton).

### TG4 — Golden fixture + regression gate (#90)
- Committed `tests/fixtures/golden/gallery/ledger.json` (render-independent skeleton) + an
  in-suite test (`test_ledger_matches_committed_golden`) asserting the recomputed ledger equals
  the committed golden byte-for-byte.

## Verification
- `tests/test_gallery.py`: 6 passed.
- Full offline suite: **839 passed** (60 warnings, all pre-existing e.g. svgo-absent).
- Offline discipline: `src/gallery.py` + `tests/test_gallery.py` import no GDAL/network/`web`/
  `tools` (verified by grep); harness + web page live outside the suite.
- Byte-identical default build: no `src/pipeline.py`, renderer, or config bytes changed; all
  Epoch 22 files are net-new and parallel to `PIPELINE_STAGES`.

## Deferred
- The real high-resolution artifact run (`tools/render_gallery.py` against real NHDPlus HR data
  on the GDAL+NAS machine) and verification of the child-tool CLI flags in the renderer bodies —
  per the Generation-1 roadmap, exercised on the GDAL+NAS machine.
