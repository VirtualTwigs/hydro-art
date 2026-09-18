# Implementation Report: CONUS Hero Image & Gallery Entry (Item #111)

## Summary

Added a CONUS (contiguous US) hero image entry to the gallery, extended the
endpoint system to accept multi-region requests without a county, created a
dedicated render script, and wired the hero image into the landing page.

## Changes

### Modified files

- **`src/endpoints.py`** — `build_endpoint_request` now accepts `region="CONUS"`
  via an explicit check (bypasses `SUPPORTED_REGIONS` lookup, which stays
  state-only to preserve `STATE_FIPS`/`REGION_BOUNDS` invariants). County
  validation skipped for CONUS. `_stem` handles empty county cleanly (no
  double-dash in filenames).

- **`src/gallery.py`** — `GallerySelection.county` changed from `str` to
  `str | None`. New CONUS entry in `GALLERY_MATRIX`: `item_id="conus-neon-hero"`,
  `region="CONUS"`, `county=None`, `style="neon-basin"`,
  `endpoint="digital_image"`.

- **`web/start.html`** — Added CONUS hero showcase section between catalog and
  "how it works". Loads the hero PNG with an `onerror` fallback placeholder.

- **`tests/fixtures/golden/gallery/ledger.json`** — Regenerated to include the
  CONUS gallery entry.

### New files

- **`tools/render_conus.py`** — Non-offline render script. Unions all 48 state
  boundaries, clips flowlines from all CONUS HUC4s, colors by HUC2 (first 2
  chars of HUC4 code → ~18 macro-basin families). CLI: `--min-order` (default 3),
  `--width` (default 8000), `--min-px`/`--max-px`. Emits SVG + PNG (via
  rsvg-convert, optional) to `output/gallery/conus-neon-hero/`.

- **`agent-os/specs/2026-09-17-conus-hero-image/`** — Spec + tasks + this report.

### Test files updated

- `tests/test_endpoints.py` — 4 new tests: CONUS accepted without county,
  non-CONUS still requires county, clean stem filename, Rights gate pass.
- `tests/test_gallery.py` — 3 new tests: CONUS in matrix, selection passes
  Rights gate, ledger includes CONUS with null county. Updated
  `test_matrix_spans_regions_styles_endpoints` for 6 entries.

## Design decisions

1. **CONUS NOT added to `SUPPORTED_REGIONS`.** Adding it broke `STATE_FIPS` and
   `REGION_BOUNDS` invariants (every supported region must have a FIPS code and
   DEM bounds). Instead, the endpoint system explicitly checks for `"CONUS"` as
   a special region value. This is minimal and avoids cascading changes.

2. **HUC2 coloring in the render script.** At continental scale, HUC4 produces
   too many visually similar groups. Using the first 2 digits of each HUC4 code
   as the grouping key gives ~18 macro-basin color families that read clearly.

3. **Gallery `county` made optional.** CONUS is a whole-network render with no
   county clip. The `GallerySelection.county` field is now `str | None = None`
   (was `str`). The ledger serializes `county: null` for CONUS.

## Verification

- Full offline suite: **1141 passed** (was 1133, +8 new), no regressions.
- Recipe roundtrip: **11/11 passed**.
- No `PIPELINE_STAGES` changes — 2D default byte-identical.
- Rights gate enforced: CONUS uses only NHDPlus HR (public domain).

## Deferred

- Real CONUS render (needs all NHDPlus HR data for 48 states extracted).
- Visual verification and gallery stamping with sha256 checksums.
- Manual browser verification of `web/start.html` hero placeholder.
