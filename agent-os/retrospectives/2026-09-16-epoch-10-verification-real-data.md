# Retrospective — Epoch 10: Verification & real-data confidence (#39–#43)

_Partially closed 2026-09-16. Three of five items shipped (#39, #40, #43); two
remain open (#41, #42's real-tile half) pending a GDAL/NAS host. This is a
partial-close retrospective: the shipped work is graded honestly, and the open
work is labeled as such._

## What the epoch was

Make the project's two long-asserted-but-unverified invariants — **byte-identical
2D output** and the **real GDAL warp/mosaic/cross-device paths** — checkable on
demand. No new `src/` product capability, no `PIPELINE_STAGES` change. The offline
suite stays green and GDAL-free; the real-data checks are deselected by default.

The motivating problem, stated in the spec's requirements: the offline suite
sometimes *asserts* invariants it cannot actually *verify*. Two concrete,
already-paid-for lessons drove the epoch — the #34 byte-identical carry-forward
(value-identical constant swap, but no double-render to prove it) and the #32
latitude-drift mosaic bug (surfaced only on real tiles, because offline fakes
exercised only the reprojector's identity short-circuit).

## What shipped

### #39 — Determinism verifier (`87c64fd`)

`src/determinism.py` — pure, stdlib-only golden-registry helper: `load_registry`
(parses `{region: sha}` JSON), `evaluate` (run-to-run + golden comparison),
`record_golden`, `format_verdict`. Importable without GDAL; 10 offline tests in
`tests/test_determinism.py`. `tools/verify_determinism.py` — non-offline CLI over
the real `Pipeline`: `--region <r> [--county <c>] [--golden <path>]`, builds twice,
captures `svg_sha256` from each, compares run-to-run and against the committed
golden. Exit 0 on all-match, non-zero with a readable diff on drift. A follow-up
fix in `1eeb81e` repaired an import path broken by a later refactor.

### #40 — Golden-output fixtures (`3835024`)

Gave the #39 verifier a committed fixture and a second checksum dimension (the DEM
mosaic). Two new pieces:

- **`src/raster.grid_checksum`** — pure/offline sha256 over a versioned header
  (`hydro-art.raster.v1`) + crs + canonical LE transform/shape + nodata sentinel +
  NaN-canonical LE float64 values. Endianness/contiguity-stable. 5 tests in
  `tests/test_raster.py`.
- **Two-checksum golden registry** — `Golden(svg_sha256, dem_mosaic_sha256=None)`
  frozen value type in `src/determinism.py`. `load_registry` parses both object
  form and #39-era bare strings. `evaluate(..., dem_sha=)` adds a soft `dem_ok`
  dimension (True/False/None). `record_golden` merges halves so recording one
  never clobbers the other. 19 total tests in `tests/test_determinism.py` (was 10
  at #39 close).
- **Committed fixture** — `tests/fixtures/golden/registry.json`, **Wahkiakum, WA**
  (smallest WA county, HUC4 1708): SVG sha `3c725d66…6457fafc` (run-to-run OK,
  cross-host invariant), DEM mosaic sha `a84769ec…a7c6ae92a` (county-scoped,
  single 3DEP tile `USGS_1_n47w124.tif`, reproducible twice — **same-host
  regression only**, GDAL/PROJ-version sensitive).
- **`tools/verify_determinism.py`** grew `--check-dem`/`--dem` with county-aware
  DEM clip (county polygon bounds, not the whole state's 3DEP). Fixed a latent
  `export_paths` str-to-`Path` crash in `_render_once`.

### #42 offline half — DEM alignment guard (`87c64fd`)

`tests/test_dem_alignment.py` — 4 tests asserting the #32 mosaic-before-warp
invariant against hand-built two-latitude grids: `normalize_dem` mosaics first
into one uniform-pixel grid, `_require_aligned` accepts `rel_tol=1e-6` warp drift
while rejecting a genuine tier change. Offline, no GDAL. The real-tile half
(acquire >=2 3DEP tiles at different latitudes, assert uniform pixel size after
warp) is bundled into #41.

### #43 — Status automation (`87c64fd`)

`src/status.py` — pure formatting core (compose last-updated line, roadmap status
stamp), stdlib-only, importable without GDAL. 10 offline tests in
`tests/test_status.py`. `tools/update_status.py` — stamps `HANDOFF.md`
last-updated line + roadmap item/epoch status from one invocation; idempotent,
prints a diff. 3 CLI smoke tests in `tests/test_update_status.py`.

## Real-data findings

The committed golden fixture (Wahkiakum, WA) was produced by two full GDAL
pipeline renders. Both SVG sha256 values matched (`3c725d66…6457fafc`), confirming
run-to-run determinism on that host. The DEM mosaic sha (`a84769ec…a7c6ae92a`) was
also reproducible across two acquisitions of the same single tile.

**The bug the real run surfaced:** `_render_once` in `tools/verify_determinism.py`
crashed after a passing SVG verdict because `export_paths` arrived as strings, not
`Path` objects — the PNG rasterization step tried `.with_suffix()` on a `str`.
Fixed in the #40 commit (`3835024`). PNG rasterization was ultimately skipped on
the smoke host (resvg unavailable); the SVG sha check stands on its own.

**SOURCE_DATE_EPOCH lesson carried forward from #57 (fulfillment):** the verifier
pins `SOURCE_DATE_EPOCH=0` for any tool-produced format it diffs, preventing
cairo's wall-clock PDF `CreationDate` from breaking byte-identity. This was
designed in, not discovered — the fulfillment epoch had already paid for it.

## Invariants held

- **Offline suite:** 644 passing at #40 close (was 527 at Epoch 9 close; the
  difference includes Epoch 12 and other intervening work). Currently 1027 passing
  (excluding the 6 unrelated `test_min_order.py` failures from proposed Epoch 26
  work).
- **2D default output byte-identical:** yes, structurally. No `PIPELINE_STAGES`
  stage touched. `grid_checksum`, the golden registry, and the status formatter
  are pure/offline and outside the pipeline. The Wahkiakum golden sha is the first
  *committed proof* that the default render is deterministic.
- **`PIPELINE_STAGES` untouched:** yes.
- **Rights gate:** N/A — this epoch added verification tooling, not renderable
  content. All source data is the same USGS federal public domain.

## Graded against pre-analysis

The #40 spec carried a `planning/pre-analysis.md` with six watch-list items.

1. **DEM checksum stability.** *Predicted:* the hash must be byte-layout-pinned
   and NaN-safe. *Outcome:* **confirmed.** `grid_checksum` uses explicit
   little-endian float64 cast, NaN normalization, and C-contiguous layout. The 5
   offline tests mutate each field (values, transform, crs, nodata) and confirm
   the hash changes. The NaN-canonical test is explicit. Grade: passed.

2. **Same-host vs cross-host honesty.** *Predicted:* risk of overselling the DEM
   sha as a portable invariant. *Outcome:* **confirmed and honestly recorded.**
   The caveat appears in the module docstring, the implementation report, the
   fixture commit message, and this retrospective. The SVG sha is the primary
   cross-host invariant; the DEM sha is opt-in (`--check-dem`), and an unrecorded
   DEM golden is a soft "record me," never a hard failure. Grade: passed.

3. **#39 regression.** *Predicted:* evolving the registry schema could break the
   shipped SVG determinism behavior. *Outcome:* **refuted.** `load_registry`
   backward-parses #39-era bare strings; the full #39 test suite survived the #40
   evolution (19 tests, all green). SVG-only registries are still expressible.
   Grade: passed.

4. **Offline-suite discipline.** *Predicted:* risk of pulling `normalize_dem` /
   rasterio into the pure core. *Outcome:* **refuted.** `determinism.py` stays
   stdlib-only (+ `src.config`). `grid_checksum` lives in the already-numpy
   `raster.py` with offline tests. DEM acquisition stays in `tools/`. Grade:
   passed.

5. **Byte-identical 2D output.** *Predicted:* nothing enters `PIPELINE_STAGES`.
   *Outcome:* **confirmed.** Structurally held — no pipeline stage touched. Grade:
   passed.

6. **Actually commit a fixture.** *Predicted:* risk of shipping more plumbing and
   no fixture. *Outcome:* **confirmed.** `tests/fixtures/golden/registry.json` is
   committed with a real county's SVG sha + DEM sha, produced by two real GDAL
   renders of Wahkiakum, WA. The mechanism-without-fixture anti-pattern was
   avoided. Grade: passed.

All six watch-list items passed. The pre-analysis was well-calibrated for this
scope.

## Carry-forwards

These are **honestly open**, not passed:

- **#41 — Real-data smoke harness.** `tools/smoke_real_paths.py` (the
  `--warp/--mosaic/--mover/--all` CLI) was never written. The three branches it
  would exercise — (a) non-identity EPSG:4269->5070 warp, (b) multi-tile mosaic
  alignment on real 3DEP tiles, (c) cross-device SMB mover — remain untested under
  a gated harness. Needs a GDAL + NAS host session. The `real_data` pytest marker
  and `pyproject.toml` deselection have not been wired.

- **#42 real-tile half.** The offline alignment guard shipped (4 tests,
  hand-built grids), but the real-tile assertion — acquire >=2 3DEP tiles at
  different latitudes and assert uniform pixel size after the single warp — is
  bundled into #41 and unbuilt.

- **Epoch gate not met.** The spec's epoch gate command
  (`verify_determinism + smoke_real_paths --all`) cannot be run because
  `smoke_real_paths.py` does not exist. The `verify_determinism` half has been run
  successfully (Wahkiakum golden match), but the full gate is open.

- **PNG determinism unverified.** `resvg` was unavailable on the smoke host;
  SVG sha byte-identity was proven, but rasterized PNG byte-identity has not been
  confirmed. The verifier degrades gracefully (warning, not failure), which is by
  design.

## Lessons

- **Ship the fixture, not just the mechanism.** The #40 pre-analysis explicitly
  called out this risk ("don't ship more plumbing and no fixture"), and the
  discipline of writing that watch-list before implementation is what kept the
  deliverable honest. The Wahkiakum golden is the epoch's most durable artifact.

- **Pre-analysis pays for itself.** All six watch-list items in `pre-analysis.md`
  were graded against reality; the predictions were accurate. This is the strongest
  argument yet for restoring the practice when it was skipped (Epoch 16's
  retrospective noted the same).

- **The offline/real split is honest but incomplete.** The epoch proved that a pure
  helper (`determinism.py`) can be fully tested offline while its real-data
  consumer (`verify_determinism.py`) exercises the GDAL branches. But the *second*
  real-data consumer (#41, the smoke harness) was never built, so the "fire exactly
  the branches fakes skip" promise is only half-delivered. The offline half is
  solid; the real-data half is the carry-forward.

- **Status automation (#43) is quiet but effective.** `tools/update_status.py`
  eliminated 3-4 hand-edit commits per epoch close. Small, well-scoped, and
  immediately useful — the kind of item that justifies its existence by being
  boring.

- **A partial close is better than a false close.** Items #41 and #42-real need a
  GDAL/NAS host. Declaring the epoch complete without them would be dishonest;
  leaving them explicitly open in the roadmap is the right call.
