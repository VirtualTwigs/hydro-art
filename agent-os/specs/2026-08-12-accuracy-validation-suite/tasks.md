# Tasks — Accuracy validation suite (roadmap #20)

## TG1 — Core error / coverage / CRS metrics (pure)

- [x] Write tests first (`tests/test_accuracy.py`): `error_metrics` exact-zero + known
      offset (rmse/max/mean); length mismatch → `AccuracyError`; skip semantics
      (None/nodata/uncovered excluded); `coverage_report` counts + fraction; `crs_report`
      verbatim incl. `None` vertical fields.
- [x] `src/accuracy.py`: `AccuracyError`, `ErrorMetrics` + `error_metrics()`,
      `CoverageReport` + `coverage_report()`, `CrsReport` + `crs_report()` (stdlib +
      `src.elevation` only, numpy-free).
- [x] Run ONLY the new tests; green.

## TG2 — Report assembly + sampler validation + QA rollup

- [x] Write tests first: `qa_rollup` sums/max across profiles; `sample_points` over a
      `GridSampler`; `build_accuracy_report` compared/skipped split; `validate_against_sampler`
      end-to-end on `_plane_grid` (exact → within_tolerance True@0; off → False; out-of-extent
      point skipped → n_uncovered); within_tolerance False when everything skipped; determinism.
- [x] `src/accuracy.py`: `QARollup` + `qa_rollup()` (structural, no `hydro_z` import),
      `AccuracyReport` (+ `within_tolerance`), `sample_points()`, `build_accuracy_report()`,
      `validate_against_sampler()`.
- [x] Run ONLY the new tests; green.

## TG3 — Verify + docs

- [x] Confirm `accuracy` imports numpy-free (offline import check); `ruff` clean.
- [x] Run the full Python suite (regression check).
- [x] Write `implementation/report.md`; tick this `tasks.md`.
- [x] Mark roadmap #20 `[x]`; update `HANDOFF.md` + `CLAUDE.md` module map. Report; STOP
      (commit is a separate explicit step).
