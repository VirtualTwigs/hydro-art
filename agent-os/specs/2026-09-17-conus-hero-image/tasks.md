# Tasks — CONUS Hero Image & Gallery Entry (#111)

Legend: `[x]` done · `[ ]` todo. Offline groups ship **tests-first** (write 2–8
tests per group, run ONLY those, then implement). `tools/` groups are
non-offline (closeout = smoke-run + record real numbers). Grade against
`planning/pre-analysis.md` (if present) at close.

## Group 1 — Config: CONUS pseudo-region in endpoint system · offline
**Dependencies:** None

- [x] 1.1 Endpoint system accepts `region="CONUS"` via explicit check in
  `build_endpoint_request` (NOT by adding CONUS to `SUPPORTED_REGIONS`, which
  would break `STATE_FIPS`/`REGION_BOUNDS` invariants). Test in `test_endpoints.py`.
- [x] 1.2 Existing `CONUS_STATES` derivation unchanged (48 states).
- [x] 1.3 Existing config tests still green (1 new test for CONUS endpoint acceptance).

**Run:** `.venv/bin/python -m pytest tests/test_config.py tests/test_endpoints.py -q`

## Group 2 — Endpoints: relax county validation for CONUS (`src/endpoints.py`) · offline
**Dependencies:** Group 1

- [x] 2.1 `build_endpoint_request` with `region="CONUS"`, `county=None` succeeds,
  returns `EndpointRequest` with `county=""`.
- [x] 2.2 Non-CONUS regions still require non-empty county (existing test).
- [x] 2.3 `_stem` produces clean filename for CONUS (no double-dash).
- [x] 2.4 CONUS + neon-basin passes Rights gate (`assert_sellable`).
  4 new tests in `tests/test_endpoints.py`.

**Run:** `.venv/bin/python -m pytest tests/test_endpoints.py -q`

## Group 3 — Gallery: optional county + CONUS entry (`src/gallery.py`) · offline
**Dependencies:** Group 2

- [x] 3.1 `GallerySelection.county` changed from `str` to `str | None`.
- [x] 3.2 CONUS entry added to `GALLERY_MATRIX` (`item_id="conus-neon-hero"`,
  `region="CONUS"`, `county=None`, `style="neon-basin"`, `endpoint="digital_image"`).
- [x] 3.3 `selection_request` passes Rights gate for CONUS entry.
- [x] 3.4 Gallery ledger includes CONUS asset with `county=null`, `sellable=true`.
- [x] 3.5 Gallery golden fixture regenerated.
- [x] 3.6 Existing `test_matrix_spans_regions_styles_endpoints` updated (6 entries, CONUS in regions).
  3 new tests in `tests/test_gallery.py`.

**Run:** `.venv/bin/python -m pytest tests/test_gallery.py -q`

## Group 4 — Render script (`tools/render_conus.py`) · non-offline
**Dependencies:** Groups 1–3

- [x] 4.1 Created `tools/render_conus.py` following `render_state_svg.py` pattern.
  CLI: `--min-order` (default 3), `--width` (default 8000), `--min-px`, `--max-px`.
  Uses HUC2 coloring (first 2 chars of HUC4 basin code). Emits SVG + PNG (via
  rsvg-convert, optional) to `output/gallery/conus-neon-hero/`. Prints sha256.
- [x] 4.2 Import-time isolation verified: `src/` modules importable without GDAL.

## Group 5 — Web: wire hero image into `web/start.html` · non-offline
**Dependencies:** Group 4

- [x] 5.1 Added CONUS hero showcase section between catalog and "how it works".
  Loads `conus-neon-hero.png` from gallery output with `onerror` fallback
  showing "coming soon" placeholder.
- [ ] 5.2 Manual verification: open `web/start.html` in a browser — placeholder
  visible; after a render, the hero image loads.

## Group 6 — Real-data smoke + validation · non-offline (record real numbers)
**Dependencies:** Groups 4–5

- [ ] 6.1 Run `tools/render_conus.py` against real NHDPlus HR data on the
  NAS/GDAL host. Record: wall-clock time, output file sizes, sha256, feature count.
  *Deferred — needs all CONUS NHDPlus HR data extracted.*
- [ ] 6.2 Verify the output visually.
  *Deferred — needs real render.*

## Group 7 — Close out + regression · offline + docs
**Dependencies:** Groups 1–6

- [x] 7.1 Full offline suite green: 1141 passed (was 1133, +8 new). No
  `PIPELINE_STAGES` edit — 2D default render byte-identical.
- [x] 7.2 Recipe roundtrip: 11/11 passed.
- [x] 7.3 Rights gate confirmed: CONUS hero uses only NHDPlus HR (public domain);
  `selection_request` enforces `assert_sellable`.
- [x] 7.4 Write `implementation/report.md`.
- [ ] 7.5 Docs sweep: update roadmap, HANDOFF.md (at commit time).
