# Specification: CONUS Hero Image & Gallery Entry (Item #111)

## Goal

Add a CONUS (contiguous US) hero image entry to the gallery matrix, extend the
gallery/endpoint system to support multi-region entries without a county, create
a dedicated `tools/render_conus.py` render script, and wire the hero image into
`web/start.html`. All offline code changes are tested; the actual render is
non-offline (needs real NHDPlus HR data for all 48 states).

## User Stories

- As a visitor, I want to see a striking continental-scale river map on the
  landing page so I immediately understand the scope and quality of the art.
- As an operator, I want a `tools/render_conus.py` script that produces a
  deterministic, rights-clean CONUS hero render with documented provenance.
- As a gallery curator, I want the CONUS entry in the gallery ledger with the
  same rights/provenance discipline as every other entry.

## Architecture

### Changes by module

**Modify: `src/gallery.py`**
- Add a `GallerySelection` for CONUS to `GALLERY_MATRIX`:
  - `item_id="conus-neon-hero"`, `region="CONUS"`, `county=None`,
    `style="neon-basin"`, `endpoint="digital_image"`,
    `rationale="Continental hero — every major river basin in the contiguous US."`
- `county` field on `GallerySelection` becomes `county: str | None = None`.

**Modify: `src/endpoints.py`**
- `build_endpoint_request`: accept `region="CONUS"` by adding `"CONUS"` to the
  region allowlist check (or checking against `CONUS_STATES` membership).
- `county` validation: when `region="CONUS"`, allow `county` to be empty/None
  (CONUS is a whole-network render, no county clip). Store `county=""` or a
  sentinel like `"CONUS"` on the request.

**Modify: `src/config.py`**
- Add `"CONUS"` to `SUPPORTED_REGIONS` so the endpoint system accepts it.
  The `build_settings` expansion to `CONUS_STATES` already handles the alias.

**New: `tools/render_conus.py`** (non-offline)
- Standalone render script following the `render_state_mono.py` pattern.
- Uses `--min-order` (default 3), `--width-preset state`, `--palette neon`,
  `--glow`, HUC2 coloring (auto via CONUS default).
- Imports `render_common` for shared recipe helpers.
- Emits SVG + PNG to `output/gallery/conus-neon-hero/`.
- Prints sha256 of each output for ledger stamping.

**Modify: `web/start.html`**
- Wire the hero image slot (`.hero .frame`) to display the CONUS hero image
  when available (static `<img>` referencing the gallery output path, with a
  fallback/placeholder when the image hasn't been rendered yet).

**Modify: `web/gallery.html`**
- No structural changes needed — the gallery page renders from the ledger JSON,
  so the CONUS entry appears automatically once `gallery_ledger()` includes it.

## Byte-identical guarantee

All changes are additive:
- `GALLERY_MATRIX` gains one entry; existing entries unchanged.
- `SUPPORTED_REGIONS` gains `"CONUS"`; existing regions unchanged.
- `EndpointRequest` county validation relaxed only for `region="CONUS"`.
- No `PIPELINE_STAGES` change. Default builds unaffected.

## Out of scope

- Actual CONUS render execution (needs all NHDPlus HR data downloaded).
- New pipeline stages or `PIPELINE_STAGES` order changes.
- Print-image or animation CONUS endpoints (hero is digital_image only).
- Multi-region `EndpointRequest` beyond CONUS (general multi-region is future work).
