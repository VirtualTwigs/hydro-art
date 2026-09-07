# Requirements — Epoch 22 (High-resolution marketing gallery, #88–90)

## Goal
Ship a curated, rights-clean marketing gallery spanning the engine's range, with a
pure/offline rights-ledger core, a render-independent golden, an opt-in high-res render
harness (deferred real run), and a self-contained web surface. No new art feature; default
build byte-identical; public-domain sources only.

## Functional requirements

### #88 Curated style matrix (offline, `src/gallery.py`)
- `GallerySelection` frozen dataclass: `item_id`, `region`, `county`, `style`, `endpoint`,
  `rationale`, plus per-endpoint params (`size`/`year`/`huc`/`formats`).
- `GALLERY_MATRIX`: a curated tuple spanning **all four regions**, **both public-domain
  styles**, and **all four endpoints** (e.g. Oregon/neon-basin/digital_image,
  Washington/elevation-tint/print_image, California/neon-basin/animation,
  Idaho/elevation-tint/digital_image, Washington/neon-basin/report). Each carries a short
  rationale (why it shows the range). Every entry must validate + be sellable.

### #90 Gallery provenance & rights ledger (offline, `src/gallery.py`)
- `selection_request(sel) -> EndpointRequest` — reuse `src.endpoints.build_endpoint_request`
  (which runs the Rights gate), so a non-sellable/invalid selection fails fast.
- `GALLERY_SCHEMA = "hydro-art/gallery-ledger@1"`.
- `gallery_ledger(selections=GALLERY_MATRIX, *, checksums=None, sources=DEFAULT_SOURCES) ->
  dict` — per-asset ledger: for each selection, its identity + rationale + `sellable` flag +
  planned deliverables (filename/kind/fmt/dims) + attribution + source versions. When
  `checksums` is given (`{item_id: {filename: sha256}}`) it must cover each asset's plan
  exactly (else `EndpointError`) and stamp per-file sha256; when `None`, checksums are null
  (render-independent skeleton). Assets sorted by `item_id`; byte-identical under `sort_keys`.

### #89 High-res render & export (opt-in, non-suite `tools/render_gallery.py`)
- CLI over the offline core: for each (or a `--item` subset) curated selection, inject the
  real renderer factories from `tools/render_endpoint.py`, render at marketing/full
  resolution, export a web-optimized derivative alongside the full-res file, compute
  checksums, and stamp a runtime `gallery_ledger` with checksums. Imports only `src/` +
  `tools.render_endpoint`; outside the suite. Real execution deferred to the GDAL+NAS machine.

### #90 Web surface (`web/gallery.html`)
- Self-contained, `file://`-safe (no build step); reads a ledger JSON (embedded sample +
  optional fetch), renders a per-asset card grid with style/endpoint/region, rationale,
  attribution, sellable badge, and the deliverable list. Uses the shared `web/shared` CSS
  foundation where practical; no top-level `document`/`window` coupling that would break other
  pages.

### #90 Golden fixture
- Commit `tests/fixtures/golden/gallery/ledger.json` = the render-independent
  `gallery_ledger()` (no checksums). In-suite test asserts the recomputed ledger equals the
  committed golden.

## Non-functional / discipline
- `src/gallery.py` + tests import ONLY stdlib + `src.*` (no GDAL/numpy/network/`web`/`tools`).
- Default 2D build byte-for-byte identical (nothing enters `PIPELINE_STAGES`).
- `tools/render_gallery.py` outside the suite.
- TDD: 2–8 focused tests first per group.

## Out of scope
- The real high-res image bytes (deferred to GDAL+NAS); CI wiring (Epoch 23); selling/checkout.

## Acceptance
- `GALLERY_MATRIX` spans four regions/both styles/four endpoints; every entry sellable.
- `gallery_ledger` byte-identical + coverage-checked + Rights-gated; golden committed + matched.
- `tools/render_gallery.py` authored, imports clean, compiles.
- `web/gallery.html` renders the ledger offline.
- Full offline suite green; default build byte-identical.
