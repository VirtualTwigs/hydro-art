# Requirements — Verification & real-data confidence (roadmap #39–#43)

## Problem

The 2026-08-27 assessment named the codebase's one structural weak seam: the
**offline suite** — its greatest strength (527+ tests, fully GDAL/network-free) —
sometimes *asserts* invariants it cannot actually *verify*, so real-data runs keep
discovering what injected fakes miss. Two concrete, already-paid-for lessons:

1. **Byte-identical output is asserted but unverified offline.** #34 (canonicalize
   `EPSG:5070`) claimed the 2D default render stayed byte-for-byte identical, but the
   offline suite has no real datasets/GDAL, so the claim was carried forward
   *unverified* (see the #34 closeout and HANDOFF's Epoch 9 note). Nothing renders a
   fixed region twice and diffs `svg_sha256`.
2. **The real GDAL paths never run in the suite.** The #32 latitude-drift mosaic bug
   only surfaced on a real WA statewide run, because the offline fakes exercised only
   the reprojector's **identity short-circuit** (`RasterioReprojector.reproject` when
   `grid.crs == dst_crs`); the real **non-identity EPSG:4269→5070 warp** (`_default_warp`
   in `src/raster_io.py`, still marked `# pragma: no cover`) had never fired under test.
   The same blind spot covers multi-tile mosaic alignment (`src/raster.normalize_dem`
   mosaic-before-warp + `_require_aligned`) and the cross-device **SMB mover**
   (`src/storage.move_file`, added only after `shutil.move`'s `os.chflags` fallback hit
   `OSError(EINVAL)` on the Synology share during the #29 migration).

Additionally, epoch bookkeeping is manual: each epoch close costs 3–4 hand-edit commits
stamping timestamps and ticking status across `HANDOFF.md` and `roadmap.md`.

## Scope (this epoch)

Make those invariants **checkable on demand** without disturbing the fully-offline
suite (roadmap Epoch 10, items #39–#43). This is verification tooling + committed
fixtures + one status script — **no new `src/` product capability** and **no change to
`PIPELINE_STAGES`**.

- **#39 Determinism verifier** — `tools/verify_determinism.py`: render a fixed region
  twice, diff `svg_sha256` (and the rasterized PNG bytes), and compare against a
  committed per-region golden hash. Closes the "#34 asserted byte-identical but couldn't
  verify offline" carry-forward.
- **#40 Golden-output fixtures for one small region** — commit a tiny county's expected
  `svg_sha256` + normalized-DEM mosaic checksum (with source-tile ids/checksums for
  provenance) so a machine *with* GDAL catches drift the offline fakes can't.
- **#41 Real-data smoke harness (opt-in, outside the offline suite)** — a `tools/`-driven
  check that fires exactly the three branches fakes skip: the reprojector's non-identity
  EPSG:4269→5070 warp, multi-tile mosaic alignment (the #32 class), and the cross-device
  SMB mover. Gated behind an env flag / pytest marker so the offline suite is untouched.
- **#42 DEM alignment invariant on real tiles** — a targeted regression asserting
  mosaicked tiles share a pixel grid *after* the single warp, on ≥2 real 3DEP tiles at
  different latitudes (the #32 bug). Ships its offline half now (the invariant against
  hand-built two-latitude grids); the real-tile half runs inside #41's gated harness.
- **#43 HANDOFF/roadmap status automation** — a small script to stamp timestamps + epoch
  status so progress bookkeeping stops costing 3–4 hand-edit commits per epoch.

## Constraints (carried from the project)

- **Byte-identical default output.** Epoch 10 adds no `src/` capability and touches no
  `PIPELINE_STAGES`, so the canonical 2D default render is trivially byte-for-byte
  unchanged — and #39 is precisely the tool that now *proves* it.
- **Offline suite stays green & GDAL-free.** No new top-level GIS imports under `src/`;
  the offline suite must not import `tools/` or require real datasets/network. The
  real-data harness (#41/#42's real half) is **deselected by default** — gated behind an
  env flag / a `real_data` pytest marker — so `pytest -q` stays exactly the offline suite.
- **`src/` never imports `tools/` or `web/`.** The verifier/harness/status scripts live
  in `tools/` and import from `src/` only (the one-way dependency holds); the offline
  suite never imports them.
- **`tools/` scripts stay outside the suite.** #39/#40/#41/#43's real behavior needs the
  full GIS/DEM environment (GDAL, `rasterio`, real datasets, the NAS/SMB share), so their
  closeout is a recorded artifact + report, not an offline unit test. Only the pure,
  synthetic-input regressions (#42's alignment invariant; any pure differ/stamp helper)
  land as offline tests in `tests/`.
- **Determinism of raster/vector-tool output.** PNG via `resvg` is metadata-free, but
  cairo-backed formats (PDF) stamp a wall-clock `CreationDate` unless `SOURCE_DATE_EPOCH`
  is pinned (learned in #57). The verifier pins `SOURCE_DATE_EPOCH=0` for any tool-produced
  format it diffs, or restricts the PNG diff to `resvg` output.

## Non-goals

- Any change to `PIPELINE_STAGES`, `Settings`, the DEM subsystem, or rendered-output
  semantics — this is verification, not new capability, and not the #32-class *fix*
  (already shipped) but its *guard*.
- Golden fixtures for every region — one tiny county is the fixture scope (#40); more
  regions can be added later by re-running the verifier.
- Wiring the DEM subsystem into `PIPELINE_STAGES` (a standing deliberate non-goal).
- A CI system — the epoch gate is a single command a human runs on a GDAL-equipped
  machine, not a hosted pipeline.

## Acceptance

- `tools/verify_determinism.py --region <r> [--county <c>]` renders twice, confirms both
  runs' `svg_sha256` are equal to each other **and** to the committed golden hash, diffs
  the rasterized PNG bytes, and exits 0 on match / non-zero with a readable diff on drift.
- A committed fixture records one tiny county's `svg_sha256` + normalized-DEM mosaic
  checksum + the source-tile ids/checksums; the offline suite can load and shape-check the
  fixture (it cannot regenerate it).
- An opt-in harness exercises, on real data, (a) the non-identity EPSG:4269→5070 warp,
  (b) multi-tile mosaic alignment, and (c) the cross-device SMB mover, producing one
  trustworthy pass/fail — and is **deselected by default** so `pytest -q` is unchanged.
- An offline regression asserts the mosaic-before-warp alignment invariant against
  hand-built two-latitude grids (the #32 guard) and is green now; the real-tile assertion
  runs inside the gated harness.
- `tools/`-driven status automation stamps the `HANDOFF.md` last-updated line and epoch
  status / roadmap ticks from one invocation; its pure formatting core is offline-tested.
- Full offline suite green (no regressions); the 2D default output is byte-identical —
  now demonstrably, via #39.
