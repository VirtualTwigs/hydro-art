# Spec — Verification & real-data confidence (roadmap #39–#43)

Verification tooling + committed fixtures + one status script that make the
project's two long-asserted-but-unverified invariants — **byte-identical 2D
output** and the **real GDAL warp/mosaic/cross-device paths** — checkable on
demand. No new `src/` capability, no `PIPELINE_STAGES` change; the offline suite
stays green and GDAL-free, and the real-data checks are deselected by default.

Grouped by roadmap item. The planning commit ships only #42's **offline** half
(the mosaic-before-warp alignment regression against hand-built grids, green now);
the rest are implemented in the follow-up per the two-command workflow, and their
closeout is a recorded artifact + report, not an offline test.

## #39 — Determinism verifier (`tools/verify_determinism.py`)

A thin, non-offline CLI over the real `Pipeline` (imports GIS eagerly, reads real
datasets — outside the offline suite, like the other real-data tools).

- `--region <r> [--county <c>] [--golden <path>]`: build the region **twice**
  through `src.pipeline.Pipeline` (reusing `build.py`'s wiring — `NAS`/local cache
  resolution, `resolve_required_files`, injected `Downloader`/`LayerLoader`/
  `SvgoOptimizer`/`FileExporter`), capturing `ctx.artifacts["svg_sha256"]` from each
  run.
- **Run-to-run**: assert `sha_run1 == sha_run2` (the `#34` carry-forward — proves the
  render is deterministic on this machine).
- **Against golden**: assert both equal the committed per-region golden hash
  (`#40`'s fixture) — this also catches drift introduced by a code change, not just
  run-to-run flakiness. A missing golden entry is a soft "record me" prompt, not a
  failure, on first run for a new region.
- **Rasterized PNG diff**: rasterize each run's SVG (reuse `tools/rasterize_layered.py`
  for the >1M-node split, or `FileExporter` PNG for small counties) and byte-compare
  the two PNGs. Pin `SOURCE_DATE_EPOCH=0` for any tool-produced format; `resvg` PNG is
  metadata-free (verify during implementation). If PNG determinism can't be guaranteed
  on a host, the PNG diff degrades to a warning and the `svg_sha256` check stands.
- Exit 0 on all-match; non-zero with a readable diff (which hash differs, run-to-run
  vs. golden, and the byte offset for PNG) on any mismatch.
- Pure seam: the *comparison + golden-registry* logic (load `{region: sha}` JSON,
  compare, format the verdict) is a small pure helper. Keep it importable without GDAL
  so it is unit-testable offline; the double-render itself is the non-offline part.

## #40 — Golden-output fixtures for one small region

The data artifact #39 and #42 consume — produced by a real GDAL render, committed once.

- Pick one **tiny county** in a supported state (small flowline count → small SVG →
  a stable, cheap-to-regenerate hash; e.g. a low-density OR/WA county). Record the
  choice + rationale in the fixture.
- Fixture file (committed, e.g. `tests/fixtures/golden/<state>-<county>.json`):
  - `svg_sha256` — the county's expected 2D-default render hash (the exact digest
    `_export_stage` computes: `hashlib.sha256(optimized_svg.encode("utf-8"))`).
  - `dem_mosaic_sha256` — checksum of the **normalized** DEM mosaic (`normalize_dem`
    base grid bytes) for the county's boundary, so a GDAL machine catches DEM-read/warp
    drift.
  - `source_tiles` — the 3DEP tile ids + per-tile checksums (from
    `acquire_dem_for_settings` provenance) that produced the mosaic, for traceability.
  - `provenance` — region/county, DEM tier, pipeline commit, and the render date.
- The offline suite may **load and shape-check** the fixture (keys present, hashes are
  64-hex) but must not try to regenerate it (no GDAL). Regeneration is a `verify_determinism`
  run on a GDAL host.

## #41 — Real-data smoke harness (opt-in, outside the offline suite)

One `tools/`-driven check that fires exactly the branches injected fakes skip, gated so
the offline suite is untouched.

- `tools/smoke_real_paths.py [--warp] [--mosaic] [--mover] [--all]` — each subcheck is
  independently runnable and reports pass/fail; `--all` is the epoch-gate roll-up.
- **(a) Non-identity warp** — acquire ≥1 real 3DEP tile (EPSG:4269 NAD83 geographic) via
  `acquire_dem_for_settings`, read it with `RasterioRasterReader`, and call
  `RasterioReprojector().reproject(grid, INTERNAL_CRS)` so the **non-identity
  `_default_warp` branch** (rasterio.warp) fires for the first time under a check — assert
  the output CRS is EPSG:5070, the transform is north-up, nodata is preserved (never
  invented), and the extent is sane.
- **(b) Multi-tile mosaic alignment** — the #42 real-tile assertion (below), invoked here.
- **(c) Cross-device SMB mover** — stage a temp file on the local disk and move it to the
  mounted NAS/SMB share via `src.storage.move_file` (the copyfile + best-effort copymode
  path that replaced `shutil.move`'s `chflags`-calling fallback); assert the bytes arrive
  intact and no `OSError(EINVAL)` is raised. Skip cleanly (not fail) when the share isn't
  mounted.
- **Gating**: register a `real_data` pytest marker and set
  `addopts = -m "not real_data"` in `pyproject.toml` so `pytest -q` stays exactly the
  offline suite; the harness runs via the `tools/` CLI (guarded by e.g.
  `HYDRO_ART_REAL_DATA=1` + a mounted-cache/NAS probe) and, where wrapped as a marked
  pytest module, only under `-m real_data`. Either way the default suite is unchanged.

## #42 — DEM alignment invariant on real tiles (offline half ships now)

A targeted regression for the #32 latitude-drift class: mosaicked tiles must share a
single pixel grid *after* the one warp.

- **Offline half (planning commit, green now)**: an offline test (in `tests/test_raster.py`
  or a new `tests/test_dem_alignment.py`) that reproduces the #32 class with **hand-built
  grids** — two source grids whose independent-warp resolutions would drift with latitude —
  and asserts that `src.raster.normalize_dem` (mosaic-before-warp) yields one grid whose
  pixels are uniform, and that `_require_aligned` accepts last-float-digit warp drift
  (`rel_tol=1e-6`) while still rejecting a genuine tier change. No GDAL, no real data.
- **Real-tile half (inside #41's gated harness)**: acquire ≥2 real 3DEP tiles at
  **different latitudes**, run them through `normalize_dem`, and assert the resulting base
  grid has a single, uniform pixel size (the drift the offline fakes can't produce). This
  is the assertion that would have caught #32 pre-merge.

## #43 — HANDOFF/roadmap status automation

A small `tools/` script that stamps the mechanical bookkeeping an epoch close repeats.

- `tools/update_status.py` — updates `HANDOFF.md`'s `_Last updated: …_` line (date +
  a one-line note) and can tick a roadmap item / stamp an epoch's status line in
  `agent-os/product/roadmap.md`. Idempotent (re-running with the same inputs is a no-op /
  same result), and prints a diff of what it changed.
- Pure core: the **formatting** (compose the last-updated line, the roadmap status stamp)
  is a small pure function, offline-unit-tested against fixed inputs; the file read/rewrite
  is the thin non-pure wrapper. Keep the pure core importable without GDAL.
- Scope guard: this replaces hand-editing *timestamps and status lines*, not the prose
  narrative — the per-item HANDOFF bullets stay hand-authored.

## Epoch gate command

A single command produces a trustworthy pass/fail without reading the code:

```
HYDRO_ART_REAL_DATA=1 .venv/bin/python tools/verify_determinism.py --region <r> --county <c> \
  && HYDRO_ART_REAL_DATA=1 .venv/bin/python tools/smoke_real_paths.py --all
```

— determinism (double-render byte-identical + golden match) **and** the real
warp/mosaic/cross-device paths, on a GDAL-equipped machine. `pytest -q` remains the
untouched offline suite.

## Test & verification plan

- #42's offline alignment regression is written and run green now (only-those-tests,
  then full suite) — the planning-commit deliverable, mirroring Epoch 9 #37.
- Any pure helpers (the #39 golden differ, the #43 status formatter) gain small offline
  unit tests when implemented.
- #39/#40/#41/#42-real are `tools/`+fixture work verified on a GDAL/NAS host: a recorded
  double-render (equal shas), the committed fixture, and the harness's three-branch
  pass/fail — captured in `implementation/report.md`, not the offline pytest suite.
- Epoch-close check: full offline suite green + the #39 verifier reports the 2D default
  output byte-identical (this is the invariant the whole epoch exists to make provable).
