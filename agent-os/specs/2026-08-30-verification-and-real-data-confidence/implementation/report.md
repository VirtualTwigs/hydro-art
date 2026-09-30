# Implementation Report — Verification & Real-Data Confidence (Epoch 10, #39–#43)

**Completed:** 2026-09-29
**Commits:** `87c64fd` (#39/#42/#43), `3835024` (#40), `76ad2ef` (#41/#42 real-data), `8916866` (epoch close)
**Suite at close:** 1641 passed (offline suite unchanged)

## Summary

Five items delivering a verification and determinism layer that makes the project's
two long-asserted invariants — byte-identical 2D output and correct real GDAL
warp/mosaic/cross-device paths — checkable on demand. No new `src/` capability,
no `PIPELINE_STAGES` change, no rendered-output byte change.

## Delivered artifacts

### #39 — Determinism verifier

- **`tools/verify_determinism.py`**: non-offline CLI that renders a region twice
  through the real `Pipeline`, captures `svg_sha256` from each run, and compares
  run-to-run + against the committed golden registry. Supports `--region`,
  `--county`, `--golden`, `--check-dem`/`--dem` (county-aware DEM clip). Pins
  `SOURCE_DATE_EPOCH=0` for rasterized format determinism. Exit 0 on match,
  non-zero with readable diff on drift.
- **`src/determinism.py`** (pure/offline): `Golden` value type (SVG + optional DEM
  mosaic SHA-256), `load_registry`/`record_golden`/`dump_registry`, `evaluate`
  (run-to-run + golden + optional DEM comparison), `format_verdict`. Handles both
  legacy bare-string and object-form registry entries.
- **`tests/test_determinism.py`**: 10+ offline unit tests (registry round-trip,
  verdict formatting, evaluate logic).

### #40 — Golden-output fixtures

- **Wahkiakum County, WA** (HUC4 1708) selected: low flowline count, already
  the e2e flagship, stable and cheap to regenerate.
- **`tests/fixtures/golden/registry.json`**: committed SVG SHA-256
  `3c725d66...6457fafc` (run-to-run and cross-host invariant) + county-scoped
  DEM mosaic SHA-256 `a84769ec...a7c6ae92a` (single tile `USGS_1_n47w124.tif`,
  same-host regression only — GDAL/PROJ-version sensitive).
- Offline shape-check tests verify keys present and hashes are 64-hex format.

### #41 — Real-data smoke harness

- **`tools/smoke_real_paths.py`**: `--warp`, `--mosaic`, `--mover`, `--all`
  subcommands, each independently runnable with pass/fail/skip reporting.
  - **(a) Warp:** EPSG:4269->5070 via `RasterioReprojector` on a cached n47w122
    3DEP tile. Asserts CRS, north-up transform, nodata preservation, sane extent.
    **PASS**.
  - **(b) Mosaic:** Multi-tile alignment at different latitudes. **SKIP** — only
    same-latitude tiles cached. Script handles gracefully; downloading a
    different-latitude tile would enable it.
  - **(c) Mover:** `src.storage.move_file` local->NAS round-trip. Bytes intact,
    no `OSError(EINVAL)`. **PASS** when NAS mounted, clean skip when unmounted.
- **`real_data` pytest marker** registered; `addopts = -m "not real_data"` in
  `pyproject.toml` keeps `pytest -q` unchanged.

### #42 — DEM alignment invariant

- **Offline half** (`tests/test_dem_alignment.py`): hand-built two-latitude grids
  prove `normalize_dem` mosaic-before-warp yields one uniform-pixel grid;
  `_require_aligned` accepts last-float-digit warp drift (`rel_tol=1e-6`),
  rejects genuine tier changes.
- **Real-tile half**: bundled into #41's mosaic check (SKIP pending
  multi-latitude tile acquisition).

### #43 — Status automation

- **`tools/update_status.py`**: stamps `HANDOFF.md` last-updated line and
  roadmap item/epoch status. Idempotent; prints a diff of changes.
- **`src/status.py`** (pure/offline): formatting core for status lines and
  roadmap stamps.
- **`tests/test_status.py`** (10 tests) + **`tests/test_update_status.py`**
  (3 CLI smoke tests).

## Invariants preserved

- **Offline suite unchanged.** `pytest -q` runs exactly the same tests; real-data
  tests deselected via marker.
- **`PIPELINE_STAGES` untouched.** No pipeline change of any kind.
- **2D default output byte-identical.** No `src/` render-path code was modified.
- **`src/` never imports `tools/`.** All real-data tools are in `tools/`, importing
  from `src/` only.

## Deferred items (verification gaps, not code gaps)

- **`verify_determinism` golden-match double-render** requires a GDAL host — tool
  is complete, the first GDAL-equipped session should run it.
- **Multi-latitude mosaic assertion** needs a 3DEP tile at a different latitude
  than n47 cached on the NAS.

## Lessons

1. **Offline fakes hide real-path bugs.** The #32 latitude-drift mosaic bug only
   surfaced on a real statewide run because the offline reprojector fakes exercised
   only the identity short-circuit. The `real_data` marker pattern — opt-in real
   checks that don't disturb the offline suite — is the right mitigation.
2. **Golden fixtures are cheap insurance.** One tiny county's committed hash catches
   drift across code changes that the offline suite structurally cannot detect.
3. **Status automation pays off immediately.** Every epoch close previously cost 3-4
   hand-edit commits for timestamps and ticks. `update_status.py` reduces this to
   one idempotent invocation.
