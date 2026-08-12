# Implementation report — Accuracy validation suite (roadmap #20)

## What shipped

`src/accuracy.py` — a pure, offline, numpy-free suite that quantifies how accurately the
elevation subsystem samples known ground truth and rolls up the CRS/units/coverage/QA
facts into an auditable `AccuracyReport`. First Epoch 5 (quality) item.

## Public API (`src/accuracy.py`)

- `AccuracyError(ElevationError)` — boundary-validation failures (length mismatch,
  negative tolerance).
- `ErrorMetrics` + `error_metrics(expected, sampled)` — `n_compared`, `n_skipped`,
  `max_abs_error_m`, `mean_abs_error_m`, `rmse_m`, per-point `residuals` (sampled −
  expected). A point is compared only when both truth and sample are non-`None`; nodata /
  uncovered / missing-truth points are **skipped** (never counted as zero error). Metrics
  are `None` when nothing was compared. RMSE/mean use stdlib `math` only.
- `CoverageReport` + `coverage_report(samples)` — `n_total`/`n_covered`/`n_nodata`/
  `n_uncovered` + a `coverage` fraction (the "nodata coverage" the roadmap asks for).
- `CrsReport` + `crs_report(provenance)` — `horizontal_crs`, `vertical_crs`,
  `vertical_units`, `resolution_m`, surfaced verbatim from `ElevationProvenance` (`None`
  stays `None`).
- `QARollup` + `qa_rollup(profiles)` — aggregates river-profile QA (vertices, nodata
  vertices, inversions, worst `max_inversion_m`) across lines. Accepts profiles
  *structurally* (any object with the four `ProfileQA` fields) so the module never imports
  the numpy-backed `hydro_z` chain.
- `AccuracyReport` (metrics + coverage + crs + qa + `tolerance_m`) with a
  `within_tolerance` property — True iff at least one point was compared and its worst
  error is within tolerance. Inversions are **reported**, not folded into the vertical
  pass/fail (they are a render-time concern, off by default per the elevation policy).
- `sample_points(sampler, points)` and `validate_against_sampler(...)` — sample a DEM
  through the injected `ElevationSampler` seam (`GridSampler`/`sample_bilinear`) and
  assemble the full report from a known DEM + points + expected truths.

## Design / guardrails honored

- **numpy-free & GDAL-free**: importing `src.accuracy` pulls in no numpy / geopandas /
  shapely / networkx / `src.raster` / `src.hydro_z` / `src.terrain` (verified: "heavy
  modules pulled in: none"). It imports only stdlib + `src.elevation`. DEM sampling is
  reached through the duck-typed `SamplerLike` protocol, so the suite stays offline and
  the test suite stays GDAL-free.
- **Nodata never invented**: a sample contributes a value only when `covered and not
  nodata`; otherwise it is skipped — never zero-filled or synthesized.
- Reuses `ElevationSample`, `ElevationProvenance`, and (structurally) `ProfileQA`
  unchanged; no edits to other modules. Not wired into `PIPELINE_STAGES` (the elevation
  subsystem is a parallel offline model validated out-of-band).

## Tests (`tests/test_accuracy.py`, 19 tests)

Reuse the tilted-plane fixture (`value == x_center + y_center`, exact under bilinear) and
`GridSampler`, so every expected truth is hand-computed. Coverage: `error_metrics`
exact-zero / known-offset (rmse = √(14/3)) / skip semantics / all-skipped → `None`
metrics / length mismatch; `coverage_report` counts + fraction + empty; `crs_report`
verbatim incl. `None` vertical fields; `qa_rollup` sum/max + empty; `sample_points` over a
`GridSampler`; `build_accuracy_report` compared/skipped split + mismatch/negative-tolerance
raises; `validate_against_sampler` end-to-end (exact → within_tolerance True@0; off-by-1 →
False@0, True@1; out-of-extent point skipped → `n_uncovered`); `within_tolerance` False
when all skipped; determinism (dataclass equality).

## Verification

- `tests/test_accuracy.py`: **19 passed**.
- Full suite: **380 passed** (was 361), no regressions.
- numpy-free import verified.
- `ruff` not installed in this `.venv`, so lint was not run here; code follows the
  repo conventions (`from __future__ import annotations`, frozen dataclasses, docstrings,
  88-col).

## Not done / follow-ups

- **Real-DEM harness deferred** (out of scope): running against downloaded 3DEP tiles
  needs the GIS stack / NAS. A thin `tools/accuracy_report.py` over `normalize_dem` output
  could follow; this item ships the fixture-tested engine the harness would call.
- Horizontal/planimetric accuracy is out of scope — this validates vertical sampling
  accuracy + coverage/QA reporting only.
