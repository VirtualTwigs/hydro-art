# Epoch 10 Retrospective — Verification & Real-Data Confidence

**Date:** 2026-09-29 (closeout)
**Items:** #39–#43
**Suite at close:** 1641 passed (offline suite unchanged by real-data additions)

## What shipped

Five items delivering a verification and determinism layer:

- **#39** `tools/verify_determinism.py` — double-render determinism checker with golden
  registry comparison. Pure `src/determinism.py` (offline-testable) holds the registry,
  golden differ, and verdict formatting.
- **#40** Golden fixtures — Wahkiakum, WA (HUC4 1708) SVG + DEM mosaic SHA-256 committed
  in `tests/fixtures/golden/registry.json`. Shape-check tests (keys, hex format) run
  offline.
- **#41** `tools/smoke_real_paths.py` — real-data smoke harness exercising the branches
  offline fakes skip: EPSG:4269→5070 warp (PASS), multi-tile mosaic alignment (SKIP —
  same-latitude tiles cached), cross-device SMB mover (PASS on NAS). `real_data` pytest
  marker keeps the offline suite unchanged.
- **#42** DEM alignment on real tiles — offline regression in `tests/test_dem_alignment.py`
  (hand-built two-latitude grids prove mosaic-before-warp yields uniform pixels); real-tile
  assertion bundled into #41's mosaic check.
- **#43** `tools/update_status.py` — status automation with pure `src/status.py` core.

## What went well

- **Offline/real split is clean.** The `real_data` marker and `addopts = -m "not real_data"`
  in `pyproject.toml` keep the offline suite untouched. Real-data tests run only when
  explicitly requested.
- **Golden registry is extensible.** Adding a new county is one `record_golden` call +
  a commit. The registry handles both SVG-only and SVG+DEM entries.

## What to watch

- **`verify_determinism` golden-match not yet run.** The tool is implemented but the
  double-render requires a GDAL environment. This is a verification gap, not a code gap —
  the first GDAL-equipped session should run it.
- **Mosaic alignment test needs multi-latitude tiles.** Only same-latitude 3DEP tiles are
  cached on the NAS. Downloading a tile at a different latitude would enable the real
  mosaic-alignment assertion.
