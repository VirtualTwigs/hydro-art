# Requirements — Accuracy validation suite (roadmap #20)

## Problem

Epochs 2–4 build a DEM-backed elevation/terrain/hydrography-Z subsystem
(`src/elevation.py`, `raster.py`, `terrain.py`, `hydro_z.py`, `mesh.py`) whose whole
value proposition is that heights are *accurate* — sampled from a documented bare-earth
DEM with a stated CRS/units. But there is **no** capability that quantifies that accuracy:
nothing compares sampled terrain/river vertices against a known DEM truth, and nothing
rolls up the CRS/units/nodata-coverage/QA facts into an auditable report. #20 adds that
suite — the first Epoch 5 (quality) item.

## Functional requirements

- **Error metrics** — given expected ("truth") elevations for a set of points and the
  values sampled from a DEM fixture at those same points, compute `max_abs_error_m`,
  `mean_abs_error_m`, `rmse_m`, per-point `residuals` (sampled − expected), and the
  compared/skipped counts. Points that are nodata, uncovered, or lack a truth value are
  **skipped** (never counted as zero error, never substituted with synthetic height).
- **Coverage report** — from a sequence of `ElevationSample`s, report totals:
  `n_total`, `n_covered`, `n_nodata`, `n_uncovered`, and a `coverage` fraction. This is
  the "nodata coverage" the roadmap calls for.
- **CRS / units report** — surface the source `horizontal_crs`, `vertical_crs`,
  `vertical_units`, and `resolution_m` directly from the fixture's
  `ElevationProvenance` (verbatim; `None` stays `None`, never invented).
- **Downstream QA rollup** — accept the existing `ProfileQA` results (river-profile
  inversion QA from `hydro_z.py`) and aggregate them: total vertices, total nodata
  vertices, total inversions, and the worst `max_inversion_m`.
- **Accuracy report** — an immutable `AccuracyReport` bundling metrics + coverage + CRS +
  QA rollup, plus a `tolerance_m` and a derived `within_tolerance` verdict
  (`max_abs_error_m <= tolerance_m`, and no skipped-everything degenerate case).
- **Sampler-driven convenience** — `validate_against_sampler(...)` samples a DEM through
  the existing `ElevationSampler` seam (`GridSampler`/`sample_bilinear`) at the query
  points and assembles the full report, so a caller passes a known DEM + points +
  expected values and gets a verdict.

## Non-functional / guardrails

- Pure, deterministic, **offline** and **numpy-free**: `src/accuracy.py` imports only
  stdlib (`math`, `dataclasses`, `typing`) + `src.elevation` (which is itself numpy-free).
  The DEM sampling is reached through the injected `ElevationSampler` protocol
  (duck-typed `.sample(x, y) -> ElevationSample`), so the suite never imports `raster`
  (numpy) or GDAL and the test suite stays GDAL-free.
- Reuse the existing value objects — `ElevationSample`, `ElevationProvenance`,
  `ProfileQA` — rather than defining parallel ones. No changes to those modules.
- Errors fail fast: mismatched `points`/`expected` lengths raise `AccuracyError`
  (subclass of `ElevationError`), consistent with the boundary-validation convention.
- Matching `tests/test_accuracy.py`; reuse the established synthetic-grid fixture
  patterns (`_plane_grid`, `GridSampler`, `build_provenance`) so truths are hand-computed
  and exact under bilinear interpolation.

## Out of scope

- Running against real, non-fixture DEM downloads (needs the GIS stack / NAS). An
  optional `tools/` harness over real 3DEP data can follow later; this item ships the
  pure, fixture-tested engine.
- Wiring into `PIPELINE_STAGES` — the elevation subsystem is a parallel offline model and
  the accuracy suite validates it out-of-band, same as the other Epoch 2–4 modules.
- Horizontal (planimetric) accuracy or reprojection error analysis — this item validates
  vertical/elevation sampling accuracy and coverage/QA reporting only.
