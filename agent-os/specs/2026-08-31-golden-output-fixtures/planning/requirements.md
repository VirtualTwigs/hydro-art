# Requirements — Golden-output fixtures for one small region (roadmap #40)

_Epoch 10 (Verification & real-data confidence), Phase 10.1._

## The ask (verbatim)

> **#40** Golden-output fixtures for one small region — commit a tiny county's
> expected SVG hash + DEM mosaic checksum so a machine *with* GDAL catches drift
> the offline fakes can't. `M`

## Context

Epoch 10 makes the codebase's asserted-but-unverifiable invariants (byte-identical
output; the real GDAL/warp/mosaic paths) *checkable on demand* without disturbing
the fully-offline suite.

**#39 already shipped the mechanism** (commit `87c64fd`):
- `src/determinism.py` — the pure, GDAL-free golden-registry + verdict core
  (`load_registry`/`evaluate`/`record_golden`/`format_verdict`, `DeterminismVerdict`).
  Registry is a `{key: svg_sha256}` JSON map.
- `tools/verify_determinism.py` — the non-offline double-render CLI that renders a
  region twice through the real `Pipeline`, diffs `svg_sha256` + a `SOURCE_DATE_EPOCH=0`
  rasterized PNG, and records/verifies against the golden registry.

**What is still missing (this item):**
1. The registry only fingerprints the **SVG**. #40 explicitly pairs the SVG hash
   with a **DEM mosaic checksum** — the fingerprint of `src.raster.normalize_dem`'s
   output for the region, i.e. the real GDAL **mosaic-before-warp** path that the
   offline fakes (`tests/test_dem_alignment.py`) can only *simulate*. This is the
   #32 latitude-drift class of bug: a golden here catches drift a fake can't.
2. **No golden fixtures are committed yet** — `tests/fixtures/golden/registry.json`
   does not exist. #40 is where a tiny county's actual expected values land in the repo.

## Functional requirements

1. **DEM mosaic fingerprint (pure, offline).** A canonical, reproducible sha256 of a
   `RasterGrid` (the `normalize_dem` `base` mosaic): identical grids → identical hash;
   any change to values / transform / CRS / nodata → different hash. Endianness- and
   platform-stable (canonical little-endian float64 byte layout). NaN handled
   canonically. Lives in `src/raster.py` (numpy is already allowed there); offline-tested.
2. **Two-checksum golden registry (pure, offline).** Evolve `src/determinism.py` so a
   golden entry carries the SVG sha **and** an optional DEM mosaic sha. `evaluate`
   compares both (SVG run-to-run + golden as today; DEM against golden); `record_golden`
   records both; `format_verdict` reports both; `load_registry` parses the richer
   schema. A missing DEM golden is a soft "record me", never a hard failure (mirrors the
   existing SVG-unrecorded behavior). The offline suite stays green.
3. **CLI wiring (non-offline).** `tools/verify_determinism.py` optionally computes the
   region's DEM mosaic checksum (acquire/normalize DEM → `grid_checksum`) and feeds it
   into `evaluate`/`record_golden`. DEM verification is opt-in (a `--dem`/`--check-dem`
   flag) so the pure-2D determinism check still runs without touching the DEM subsystem.
   The DEM half degrades to a clear skip when the DEM subsystem/tiles are unavailable —
   the SVG check stands (mirrors the existing best-effort PNG behavior).
4. **Committed fixture.** Record and commit a **tiny county's** golden entry (SVG sha,
   plus the DEM mosaic sha when a GDAL/NAS host can produce it) to
   `tests/fixtures/golden/registry.json`.

## Non-functional / invariants (hard)

- **Offline-suite discipline held.** `src/determinism.py` stays stdlib-only (+`src.config`);
  the array→sha helper lives in `src/raster.py` (numpy-only, already offline-tested). No new
  GDAL/network import in `src/` or `tests/`. The DEM acquisition/normalization stays in `tools/`.
- **2D default output byte-identical.** Nothing enters `PIPELINE_STAGES`; the DEM subsystem
  stays parallel and un-wired. No rendered bytes change.
- **#39's shipped behavior preserved in spirit.** The SVG run-to-run + golden semantics are
  unchanged; only the registry value schema grows (SVG-only is still expressible).

## Honesty caveats (to record, not hide)

- A **DEM mosaic checksum is a same-host regression**, not a cross-host invariant: real
  GDAL/PROJ warp output can differ by GDAL/PROJ version and platform. The golden proves
  "this host's `normalize_dem` didn't drift" and catches code-level drift — exactly #40's
  intent ("a machine *with* GDAL catches drift the offline fakes can't"). The SVG sha is
  the stronger, pure-Python, cross-host invariant.
- If the in-session GDAL/NAS host cannot cheaply acquire the county's 3DEP tiles, the **DEM
  half of the committed fixture** is recorded on the GDAL/NAS host as the epoch-gate
  closeout (mirroring how #42's real-tile half is handled) — the *code path* is complete and
  offline-tested regardless.

## Out of scope

- The real-data smoke harness / cross-device mover (#41) and the real-tile alignment
  regression (#42's real half) — separate items.
- Any change to the 2D pipeline, `Settings`, or rendered output.
