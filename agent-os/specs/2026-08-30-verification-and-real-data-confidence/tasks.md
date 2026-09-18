# Tasks — Verification & real-data confidence (roadmap #39–#43)

## TG0 — Planning & the alignment regression (this commit)
- [x] Add Epoch 10 (#39–#43) to `agent-os/product/roadmap.md` (already present).
- [x] Write spec artifacts (`planning/requirements.md`, `spec.md`, `tasks.md`).
- [x] Write the offline #42 alignment regression (`tests/test_dem_alignment.py`):
      hand-built two-latitude grids → `normalize_dem` mosaic-before-warp yields
      one uniform-pixel grid; `_require_aligned` accepts `rel_tol=1e-6` warp drift,
      rejects a real tier change. Offline, no GDAL.
- [x] Run ONLY that test green.
- [x] Commit planning + the alignment regression (leave #39/#40/#41-real/#43 for implement).

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
- [x] Pick a small OR/WA county; record choice + rationale.
      **Washington/Wahkiakum** — low flowline count, already used as the e2e
      flagship, golden hashes committed in `tests/fixtures/golden/registry.json`.
- [x] Real GDAL render → commit `tests/fixtures/golden/registry.json`:
      `svg_sha256`, `dem_mosaic_sha256`, provenance.
- [x] Offline shape-check test (keys present, 64-hex hashes); no regeneration
      offline. 2 new tests in `tests/test_determinism.py`.

## TG3 — Real-data smoke harness (#41) + #42 real-tile assertion
- [x] `tools/smoke_real_paths.py --warp/--mosaic/--mover/--all`.
- [x] (a) Non-identity EPSG:4269→5070 warp: read a real 3DEP tile →
      `RasterioReprojector().reproject(…, INTERNAL_CRS)` fires `_default_warp`;
      assert CRS/north-up/nodata/extent. **PASS** on cached n47w122 tile.
- [x] (b) Multi-tile mosaic alignment on ≥2 real tiles at different latitudes →
      `normalize_dem` base grid has one uniform pixel size (#42 real half / #32 guard).
      **SKIP** — only 2 cached tiles at same latitude (n47). Downloads a tile at a
      different latitude to enable. Script handles gracefully.
- [x] (c) Cross-device SMB mover: `src.storage.move_file` local→NAS, bytes intact,
      no `OSError(EINVAL)`; skip cleanly when unmounted. **PASS**.
- [x] Gate: register `real_data` pytest marker + `addopts = -m "not real_data"` in
      `pyproject.toml`. `pytest -q` is unchanged (1144 passed).

## TG4 — Status automation (#43)
- [x] `tools/update_status.py`: stamp `HANDOFF.md` last-updated line + roadmap
      item/epoch status; idempotent; prints a diff.
- [x] Pure formatting core (`src/status.py`) importable without GDAL; offline unit
      tests (`tests/test_status.py` 10 + `tests/test_update_status.py` 3 CLI smoke).

## Closeout
- [x] Full offline suite green (1144 passed, no regressions); `pytest -q` unchanged
      (marker deselected).
- [x] Recipe roundtrip: 11/11 passed.
- [x] On a GDAL/NAS host, `smoke_real_paths --all`: warp PASS, mosaic SKIP (same-lat
      tiles), mover PASS.
- [ ] Run `verify_determinism` for the golden-match check (double-render
      byte-identical + golden match). *Deferred — long-running real render.*
- [ ] Tick Epoch 10 items `[x]` in the roadmap; write retrospective.
