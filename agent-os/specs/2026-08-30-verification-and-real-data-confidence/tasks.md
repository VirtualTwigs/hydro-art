# Tasks — Verification & real-data confidence (roadmap #39–#43)

## TG0 — Planning & the alignment regression (this commit)
- [x] Add Epoch 10 (#39–#43) to `agent-os/product/roadmap.md` (already present).
- [x] Write spec artifacts (`planning/requirements.md`, `spec.md`, `tasks.md`).
- [x] Write the offline #42 alignment regression (`tests/test_dem_alignment.py`):
      hand-built two-latitude grids → `normalize_dem` mosaic-before-warp yields
      one uniform-pixel grid; `_require_aligned` accepts `rel_tol=1e-6` warp drift,
      rejects a real tier change. Offline, no GDAL.
- [x] Run ONLY that test green.
- [ ] Commit planning + the alignment regression (leave #39/#40/#41-real/#43 for implement).

## TG1 — Determinism verifier (#39)
- [x] `tools/verify_determinism.py` (non-offline): `--region/--county/--golden`,
      build twice via the real `Pipeline`, capture each `svg_sha256`.
- [x] Assert run-to-run equal + equal to the committed golden; readable diff +
      non-zero exit on drift (missing golden = soft "record me").
- [x] Rasterized PNG diff (reuse `rasterize_layered.py` / `FileExporter`), pin
      `SOURCE_DATE_EPOCH=0`; degrade to warning if PNG determinism unverifiable.
- [x] Pure golden-differ/registry helper (`src/determinism.py`) importable without
      GDAL; small offline unit test (`tests/test_determinism.py`, 10 tests).

## TG2 — Golden fixtures for one tiny county (#40)
- [ ] Pick a small OR/WA county; record choice + rationale.
- [ ] Real GDAL render → commit `tests/fixtures/golden/<state>-<county>.json`:
      `svg_sha256`, `dem_mosaic_sha256`, `source_tiles` (ids+checksums), provenance.
- [ ] Offline shape-check test (keys present, 64-hex hashes); no regeneration offline.

## TG3 — Real-data smoke harness (#41) + #42 real-tile assertion
- [ ] `tools/smoke_real_paths.py --warp/--mosaic/--mover/--all`.
- [ ] (a) Non-identity EPSG:4269→5070 warp: acquire a real 3DEP tile →
      `RasterioReprojector().reproject(…, INTERNAL_CRS)` fires `_default_warp`;
      assert CRS/north-up/nodata/extent.
- [ ] (b) Multi-tile mosaic alignment on ≥2 real tiles at different latitudes →
      `normalize_dem` base grid has one uniform pixel size (the #42 real half / #32 guard).
- [ ] (c) Cross-device SMB mover: `src.storage.move_file` local→NAS, bytes intact,
      no `OSError(EINVAL)`; skip cleanly when unmounted.
- [ ] Gate: register a `real_data` pytest marker + `addopts = -m "not real_data"` in
      `pyproject.toml`; CLI guarded by `HYDRO_ART_REAL_DATA=1` + a mount probe.
      Confirm `pytest -q` is byte-for-byte the same offline suite.

## TG4 — Status automation (#43)
- [x] `tools/update_status.py`: stamp `HANDOFF.md` last-updated line + roadmap
      item/epoch status; idempotent; prints a diff.
- [x] Pure formatting core (`src/status.py`) importable without GDAL; offline unit
      tests (`tests/test_status.py` 10 + `tests/test_update_status.py` 3 CLI smoke).

## Closeout
- [ ] Full offline suite green (no regressions); `pytest -q` unchanged (marker deselected).
- [ ] On a GDAL/NAS host, run the epoch-gate command: `verify_determinism` reports
      double-render byte-identical + golden match, `smoke_real_paths --all` passes the
      three branches. Record the artifacts (equal shas, fixture, harness pass/fail) +
      any integration wrinkles in `implementation/report.md`.
- [ ] Tick Epoch 10 items `[x]` in the roadmap; add an `agent-os/retrospectives/` closeout
      note when the epoch lands.
