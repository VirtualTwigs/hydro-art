# Spec — Golden-output fixtures for one small region (roadmap #40)

_Epoch 10, Phase 10.1. Builds on #39's shipped determinism verifier._

## Goal

Commit a tiny county's expected **SVG hash** and **DEM mosaic checksum** as golden
fixtures, and extend the determinism verifier so a GDAL-equipped machine catches the
real warp/mosaic drift the offline fakes can only simulate. No product capability;
no rendered-bytes change; offline suite stays green.

## Design

### 1. `src/raster.py` — `grid_checksum(grid) -> str` (pure, offline)

A canonical sha256 fingerprint of a `RasterGrid` — the DEM-subsystem counterpart of
`svg_sha256`. Hashes, in a fixed order:

- a short header (`"hydro-art.raster.v1"`) so the scheme is versioned;
- `crs` (utf-8);
- the transform four-tuple and grid shape as canonical little-endian float64/int64;
- `nodata` (a sentinel token when `None`);
- the values as **C-contiguous little-endian float64** bytes, with NaN normalized to a
  single canonical bit pattern so `nan != nan` can't make an otherwise-identical grid
  hash differently.

Pure numpy + `hashlib`; no new imports beyond what `raster.py` already has. `normalize_dem`
is untouched — the checksum is computed by callers (the CLI) on its `base` grid.

### 2. `src/determinism.py` — two-checksum golden (pure, offline)

Evolve the registry value from a bare sha string to a small structure carrying an SVG sha
(required) and an optional DEM mosaic sha. Concretely:

- **Golden value type.** A frozen `Golden(svg_sha256: str, dem_mosaic_sha256: str | None)`.
- **`load_registry`** parses `{key: {"svg_sha256": <sha>, "dem_mosaic_sha256": <sha>?}}`.
  For resilience it also accepts a bare string value as an SVG-only golden (so a hand-authored
  or #39-era flat entry still loads). Every sha validated as 64-hex.
- **`evaluate(key, run_shas, registry, *, dem_sha=None)`** keeps the SVG run-to-run + golden
  logic and adds DEM golden comparison: `dem_ok` is `True`/`False` when a DEM golden exists and
  `dem_sha` is supplied, else `None` (soft "record me" / not-checked). `DeterminismVerdict`
  gains `dem_sha`, `golden_dem_sha`, `dem_ok`; `ok` also requires `dem_ok is not False`;
  `needs_recording` covers "svg stable and (svg or dem golden missing)".
- **`record_golden`** records the stable SVG sha and, when a `dem_sha` is present on the
  verdict, the DEM sha too — merging (not clobbering) an existing entry's other half.
- **`format_verdict`** adds a `dem:` line (MATCH / MISMATCH / none-recorded / not-checked).

The module stays stdlib-only (+`src.config`).

### 3. `tools/verify_determinism.py` — DEM checksum wiring (non-offline)

Add opt-in DEM verification:
- `--check-dem` computes the region's DEM mosaic checksum and includes it in the verdict.
- A supplied `--dem <path.npy>` loads an already-normalized/mosaicked grid (fast, offline-ish
  experiments); otherwise the CLI acquires real 3DEP relief for the region and normalizes it
  via the existing `src.dem.acquire_dem_for_settings` → `src.raster.normalize_dem` (the
  `src.raster_io` reader/reprojector, #31) path, clipped to the region — reusing the exact
  wiring `tools/render_terrain_print.py` already uses.
- DEM computation degrades to a clear "skipped" line (SVG check stands) on any DEM error, so
  the pure-2D determinism check never regresses.
- `--record` writes both halves it has.

### 4. Committed fixture — `tests/fixtures/golden/registry.json`

Record a **tiny county** end-to-end on the GDAL/NAS host and commit its entry. Candidate: the
smallest available county with staged NHDPlus datasets (e.g. a small WA/OR county). The SVG sha
is the primary, cross-host value; the DEM mosaic sha is recorded when the host can acquire the
county's 3DEP tiles cheaply, else deferred to the GDAL/NAS host per the #42 precedent and noted
in the fixture + report.

## Files

- `src/raster.py` — add `grid_checksum` (+ `__all__` if present).
- `tests/test_raster.py` — offline tests for `grid_checksum`.
- `src/determinism.py` — `Golden`, evolved `load_registry`/`evaluate`/`record_golden`/
  `format_verdict`/`DeterminismVerdict`.
- `tests/test_determinism.py` — update for the two-checksum schema.
- `tools/verify_determinism.py` — DEM checksum wiring + flags.
- `tests/fixtures/golden/registry.json` — committed golden(s).
- `agent-os/specs/2026-08-31-golden-output-fixtures/implementation/report.md`.

## Verification

- Offline: only the new/updated tests during each group, then the **full suite** (regression).
- Non-offline: run `tools/verify_determinism.py --region <R> --county <C> [--check-dem] --record`
  on the GDAL/NAS host; record the numbers in `tasks.md`.
- 2D default output byte-identical (structural: no `PIPELINE_STAGES` touched).
