# Spec — Accuracy validation suite (roadmap #20)

## Summary

A new pure module `src/accuracy.py` that quantifies the elevation subsystem's accuracy:
it compares sampled terrain/river vertices against a known DEM fixture, and reports
horizontal/vertical CRS, units, nodata coverage, and downstream river-profile QA. It is
numpy-free and offline — DEM sampling is reached through the existing `ElevationSampler`
seam (`.sample(x, y) -> ElevationSample`), and it reuses `ElevationSample`,
`ElevationProvenance`, and `ProfileQA` unchanged.

## Value objects (all `@dataclass(frozen=True)`)

```python
class AccuracyError(ElevationError): ...   # boundary-validation failures

@dataclass(frozen=True)
class ErrorMetrics:
    n_compared: int              # points with both a truth and a covered, non-nodata sample
    n_skipped: int               # points skipped (nodata / uncovered / no truth)
    max_abs_error_m: float | None    # None when n_compared == 0
    mean_abs_error_m: float | None
    rmse_m: float | None
    residuals: tuple[float, ...]     # sampled - expected, one per compared point, in order

@dataclass(frozen=True)
class CoverageReport:
    n_total: int
    n_covered: int               # ElevationSample.covered and not nodata
    n_nodata: int                # covered but nodata
    n_uncovered: int             # not covered
    @property
    def coverage(self) -> float  # n_covered / n_total (0.0 when n_total == 0)

@dataclass(frozen=True)
class CrsReport:
    horizontal_crs: str
    vertical_crs: str | None
    vertical_units: str | None
    resolution_m: float | None

@dataclass(frozen=True)
class QARollup:
    n_lines: int
    n_vertices: int
    n_nodata: int
    n_inversions: int
    max_inversion_m: float       # 0.0 when none

@dataclass(frozen=True)
class AccuracyReport:
    metrics: ErrorMetrics
    coverage: CoverageReport
    crs: CrsReport
    qa: QARollup
    tolerance_m: float
    @property
    def within_tolerance(self) -> bool
        # True iff metrics.n_compared > 0 and metrics.max_abs_error_m <= tolerance_m
        # and qa has no inversions beyond tolerance? -> inversions reported, not gating.
```

`within_tolerance` gates on *vertical error only* (`n_compared > 0` and
`max_abs_error_m <= tolerance_m`). Inversions are **reported** in `qa`, not folded into
the pass/fail verdict (they are a render-time concern, off by default per the elevation
policy).

## Functions

- `error_metrics(expected: Sequence[float | None], sampled: Sequence[float | None]) -> ErrorMetrics`
  — `expected`/`sampled` are aligned; a point is compared only when both are non-`None`
  (callers pass `None` for nodata/uncovered samples and for missing truths). Raises
  `AccuracyError` on length mismatch. `rmse` and `mean` computed with stdlib `math` only.
- `coverage_report(samples: Sequence[ElevationSample]) -> CoverageReport`.
- `crs_report(provenance: ElevationProvenance) -> CrsReport`.
- `qa_rollup(profiles: Sequence[ProfileQA]) -> QARollup` — sums vertices/nodata/inversion
  counts, takes the max `max_inversion_m`.
- `sample_points(sampler, points: Sequence[tuple[float, float]]) -> tuple[ElevationSample, ...]`
  — calls `sampler.sample(x, y)` per point (the `ElevationSampler` seam).
- `build_accuracy_report(*, samples, expected, provenance, tolerance_m, profiles=()) -> AccuracyReport`
  — the pure assembler: derives the compared/skipped split from `samples` (a sample
  contributes a value only when `covered and not nodata`), builds all four sub-reports,
  and returns the bundle. Raises `AccuracyError` on `len(samples) != len(expected)` or
  `tolerance_m < 0`.
- `validate_against_sampler(*, sampler, points, expected, provenance, tolerance_m, profiles=()) -> AccuracyReport`
  — convenience: `sample_points` then `build_accuracy_report`.

## Skip / compare semantics (the crux)

For each index `i`, from `samples[i]` (an `ElevationSample`) derive a sampled value:
`value = samples[i].value_m if (samples[i].covered and not samples[i].nodata) else None`.
The point is **compared** iff `value is not None and expected[i] is not None`; otherwise
**skipped**. This guarantees nodata is never silently treated as 0 m and never
substituted with synthetic height (elevation policy), and truths may be sparse.

## Testing (`tests/test_accuracy.py`)

Reuse the fixture patterns from `test_terrain.py`/`test_raster.py`:
- `_plane_grid()` — a 4×4 tilted plane where `value == x_center + y_center`, exact under
  bilinear sampling, so expected truths are hand-computable.
- `GridSampler(grid)` as the injected sampler; `build_provenance(...)` for CRS/units.

Cases:
1. `error_metrics` on exact samples → zeros; on a known offset → exact rmse/max/mean.
2. Length mismatch → `AccuracyError`.
3. Skips: a `None`/nodata/uncovered sample or missing truth is excluded from
   `n_compared` and from the metrics (not counted as zero error).
4. `coverage_report` counts covered / nodata / uncovered correctly; `coverage` fraction.
5. `crs_report` passes provenance CRS/units/resolution verbatim, including `None`
   vertical fields.
6. `qa_rollup` sums counts across multiple `ProfileQA` and takes the max inversion.
7. `validate_against_sampler` end-to-end on `_plane_grid`: exact truths → `within_tolerance`
   True at tolerance 0; an off-by-more-than-tolerance truth → False; an out-of-extent
   point is skipped and shows up in `n_uncovered`.
8. `within_tolerance` is False when everything was skipped (`n_compared == 0`).
9. Determinism: same inputs → identical report (dataclass equality).

## Guardrails

- `src/accuracy.py` imports only stdlib + `src.elevation` (and `src.hydro_z.ProfileQA`
  type — import the type only; no numpy). Verify with the offline suite (no GDAL/numpy in
  `sys.modules` needed to import `accuracy`). Note: `ProfileQA` lives in `hydro_z.py`
  which imports `terrain`→`raster`→numpy; to keep `accuracy` numpy-free, `qa_rollup`
  accepts any object exposing `n_vertices/n_nodata/inversion_indices/max_inversion_m`
  (structural), and the module does **not** import `hydro_z` at module load. Tests may
  build lightweight stand-ins or import the real `ProfileQA`.
- `ruff` clean; `from __future__ import annotations`; docstrings on public API.
