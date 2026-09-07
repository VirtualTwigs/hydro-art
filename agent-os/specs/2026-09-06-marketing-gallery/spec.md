# Spec: High-resolution marketing gallery (Epoch 22, #88–90)

Fourth epoch of Generation 1: the visual proof of the engine's range for the website — a
curated, rights-clean gallery. Reuses the endpoint contract + Rights gate rather than forking
render logic; the real high-res bytes are an opt-in harness deferred to the GDAL+NAS machine.

## Design

### 1. Curated matrix + rights ledger — `src/gallery.py` (offline) — #88/#90
- `GallerySelection` frozen dataclass (identity + per-endpoint params + `rationale`).
- `GALLERY_MATRIX` — five curated selections spanning all four regions, both public-domain
  styles, and all four endpoints:
  1. Oregon · neon-basin · digital_image — flagship neon river art (SVG+PNG).
  2. Washington · elevation-tint · print_image (24x36) — archival hypsometric terrain print.
  3. California · neon-basin · animation (year 2015) — year-in-motion seasonality.
  4. Idaho · elevation-tint · digital_image — elevation-mono range across a fourth region.
  5. Washington · neon-basin · report (huc 17080003) — watershed analytics report.
- `selection_request(sel)` builds a payload and calls `src.endpoints.build_endpoint_request`,
  which runs the Rights gate — so constructing the ledger fails fast on any non-sellable or
  invalid selection.
- `GALLERY_SCHEMA = "hydro-art/gallery-ledger@1"`; `gallery_ledger(selections, *, checksums,
  sources)` emits `{schema, attribution, sources, assets:[{item_id, region, county, style,
  endpoint, rationale, sellable, deliverables:[{filename, kind, fmt, width_px, height_px,
  sha256?}]}]}` with assets sorted by `item_id`. `checksums` (optional) is coverage-checked per
  asset (reusing the exact-coverage discipline from `endpoint_manifest`); when absent the
  ledger is the render-independent skeleton (sha256 = null). Byte-identical under `sort_keys`.

### 2. High-res render harness — `tools/render_gallery.py` (#89, non-suite)
Thin CLI over the offline core: for each curated selection (or `--item <id>` subset), inject
the real renderer factories from `tools/render_endpoint.py`, render at marketing/full
resolution, export a web-optimized derivative next to the full-res file, sha256 both, and stamp
a runtime `gallery_ledger(..., checksums=...)`. Imports only `src/` + `tools.render_endpoint`
(with the standard `sys.path` insert); outside the suite. Real execution deferred to GDAL+NAS.
Exit: `EndpointError`→1, render→2.

### 3. Web surface — `web/gallery.html` (#90)
Self-contained, `file://`-safe page: an embedded sample ledger (and an optional `?ledger=`
fetch) rendered as a responsive card grid — each card shows region · style · endpoint, the
rationale, a "public-domain · sellable" badge, attribution, and the deliverable filenames.
Leans on `web/shared/ux.css` where practical; all DOM access inside function bodies so it never
breaks the Node-loadable shared JS.

### 4. Golden fixture — `tests/fixtures/golden/gallery/ledger.json` (#90)
The committed render-independent `gallery_ledger()`; an in-suite test recomputes it and asserts
equality — regression-guarding the curated matrix + rights provenance. Real per-asset checksums
stay with the `--check`/harness run on the GDAL machine (deferred).

## Discipline / invariants
- `src/gallery.py` offline (stdlib + `src.endpoints` + `src.fulfillment`); nothing enters
  `PIPELINE_STAGES` → default 2D build byte-identical.
- No GDAL/network in `src/` or `tests/`.
- `tools/render_gallery.py` outside the suite; `web/gallery.html` no build step.

## Files
- NEW `src/gallery.py`
- NEW `tests/test_gallery.py`
- NEW `tools/render_gallery.py`
- NEW `web/gallery.html`
- NEW `tests/fixtures/golden/gallery/ledger.json`
- NEW `agent-os/specs/2026-09-06-marketing-gallery/implementation/report.md`
