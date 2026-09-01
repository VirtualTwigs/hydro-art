# Spec — Watershed report analytics (roadmap #48–#55)

## Overview

Promote the analytical content of `notebooks/salmon_creek_yoy.ipynb` into a
reusable watershed report. The `{year: [n,12]}` monthly-flow series that
`src.historical_flow.yearly_flow_series` already produces is the single input to a
new **offline, numpy-only statistics layer**; all external observations are read
by `tools/` executors behind injectable provider seams and snapshotted for
reproducibility. Mirrors the #23/#25/#44 precedent; nothing here enters
`PIPELINE_STAGES` and the 2D default output stays byte-identical.

Two design rules carried from prior epochs, enforced throughout:
- **Statistics are pure `src/`; data is `tools/` behind a seam.** (offline
  discipline)
- **No duplicated recipe.** One shared plotting/loading recipe
  (`tools/report_common.py`), one shared web foundation (`ux.css`/`hydro-ux.js`) —
  the Epoch 9 anti-drift lesson.

> **Scope note (2026-08-30 revenue amendment).** This spec is **research / product
> discovery**, not a commercial deliverable. Build the analytics and validation for
> credibility, but do **not** treat the report as a sellable product: commercialization
> is gated on the Epoch 11.5 revenue outcome plus buyer-discovery interviews
> (`agent-os/product/revenue-validation-amendment.md`). **Rights gate:** the report
> derives from PRISM climate data — no PRISM-derived report or figure may be **sold**
> until a written arrangement with the PRISM Climate Group is documented or the PRISM
> dependency is replaced. USGS/NHD/WBD provenance + attribution must be recorded on any
> asset that leaves the project.

## `src/flow_metrics.py` (new, numpy-only, offline) — items #48, #49, #53 + #50, #51

**One combined analysis module** (per the 2026-09-01 realignment): the intrinsic
hydrograph / trend / spatial metrics (#48/#49/#53) below and the model-vs-observed
validation + climate-index teleconnection (#50/#51, next section) live in the single
`src/flow_metrics.py` — there is no separate `flow_validation.py`.

Pure functions over the `{year: [n,12]}` series (or a single reach's `[years,12]`
matrix). No mutation of inputs; identical inputs → identical outputs.

```python
# --- #48 intrinsic hydrograph shape ---------------------------------------
def peak_flow(series)        -> dict[int, np.ndarray]   # per-year max over months
def low_flow(series, *, months=(6,7,8)) -> dict[int, np.ndarray]  # summer minimum
def center_of_timing(monthly) -> float | np.ndarray     # month of 50% cumulative
def flashiness(monthly)      -> float | np.ndarray       # Richards-Baker (monthly)
def seasonal_ratio(monthly, *, wet=(11,12,1,2,3,4)) -> float  # wet/dry mean ratio
def flow_duration(monthly, quantiles) -> np.ndarray      # exceedance percentiles

# --- #49 trend / distribution --------------------------------------------
def mann_kendall(values) -> MannKendall   # S, tau, p, trend in {inc,dec,none}
def sens_slope(values)   -> float          # median pairwise slope
def percentile_rank(value, record) -> float
def anomaly(value, normal) -> float
def rolling_normals(values, *, window=30) -> list[Normal]  # sliding means

# --- #53 spatial decomposition -------------------------------------------
def subset_series(series, idx) -> dict[int, np.ndarray]   # membership sub-series
def outlet_index(mean_flow_per_reach, idx) -> int          # max-accumulated reach
def longitudinal_profile(accum_flow, hydroseq, dnhydroseq, path) -> np.ndarray
```

`MannKendall`, `Normal` are small frozen dataclasses. `FlowMetricsError(ValueError)`
for boundary failures (empty series, ragged shapes, window > record). Imports only
numpy; `__all__` exports the public surface.

## `src/flow_metrics.py` validation half — items #50, #51

Folded into the same `src/flow_metrics.py` module (not a separate file). Pure
comparison + correlation metrics over caller-supplied arrays. Missing values
(`nan`) are **skipped, never zero-filled** — the `src/accuracy.py` discipline.

```python
# --- #50 model vs observed ------------------------------------------------
def bias(model, obs) -> float
def pearson_r(model, obs) -> float
def nash_sutcliffe(model, obs) -> float          # 1.0 == perfect; can be < 0
def rmse(model, obs) -> float
def seasonal_skill(model_12, obs_12) -> np.ndarray   # per-month agreement
def validate(model_12, obs_12) -> ValidationReport   # rolls the above up + verdict

# --- #51 climate-index teleconnection ------------------------------------
def align_index(metric_by_year, index_by_year) -> tuple[np.ndarray, np.ndarray]
def correlate(metric_by_year, index_by_year, *, lag=0) -> float
```

`ValidationReport` is a frozen dataclass with a `verdict` in
`{good, moderate, weak}` from documented r/NSE thresholds, so the report can
*honestly* pick "validated" vs. "climatology-consistent" framing.
`FlowValidationError(ValueError)` for length/overlap failures. numpy-only.

## `tools/` executors (non-offline, behind the seams) — items #50, #51, #52

- `tools/nwis_gauge.py` — `GaugeProvider`: fetch USGS NWIS monthly-mean discharge
  for a gauge id (e.g. Salmon Creek at Battle Ground, WA), return a
  `{year: [12]}` observed series aligned to the report years. **Snapshotted** to
  the NAS (raw NWIS response + a manifest) so re-runs are offline/reproducible;
  eager `requests`/parsing lives here only.
- `tools/climate_index.py` — fetch ENSO ONI / PDO monthly/annual index (small
  public tables), snapshot to the NAS, expose `index_by_year`.
- `tools/prism_fetch.py` (extend, #52) — accept a `--start/--end` span so the
  monthly `ppt`+`tmean` archive can be staged for the **full 1895–present record**;
  idempotent/resumable, mount-aware, exactly as today.

All three keep `src/` GDAL/network-free; the offline suite injects fakes.

## Report assembly — item #54

- `tools/report_common.py` — the single shared report recipe (mirror of
  `render_common.py`): load the basin network + PRISM year series (reusing the
  `_yoy_net_<huc4>.pkl` / clip caches), select the watershed reaches, and the
  matplotlib figure recipe (watershed map, hydrograph-by-year, annual-mean-vs-peak,
  long-record trend, low-flow + stream-temp, typical-year band, validation plot,
  ENSO scatter). Both the notebook and the CLI builder call this — no divergent
  copies.
- `tools/build_watershed_report.py` — `--huc4 --huc12 … --name --start --end
  [--gauge <nwis-id>]` → the full figure set to `notebooks/figures/` (+ optional
  the neon YoY art via the existing `tools/render_watershed_yoy.py`).
- Refactor `notebooks/salmon_creek_yoy.ipynb` to import `report_common`, adding the
  new sections (long record, validation, low-flow/salmon framing, ENSO) as thin
  calls.

## Web report view — item #55 (proposed UX; see `planning/ux.md`)

A report surface over the shared foundation: metric tiles, a model-vs-gauge
validation badge, a long-record sparkline, an ENSO-overlay toggle. New shared CSS
components (`.metric-tile`, `.report-grid`, `.validation-badge`, `.chart-card`,
`.sparkline`) added to `web/shared/ux.css`; any report data/formatting helper added
to `web/shared/hydro-ux.js` (kept Node-loadable). No per-page duplication.

## Determinism & byte-identical default

- No new `src/` symbol is imported by `PIPELINE_STAGES`; the 2D pipeline and its
  default output are byte-identical.
- Every `src/` function is pure over its arrays; identical staged inputs →
  identical metrics → identical figures (given identical matplotlib, as with the
  existing render tools).
- External data is snapshotted, so a report re-runs offline from local snapshots.

## Testing (offline)

New offline suites, injecting fakes + hand-built arrays with **known answers** (the
task list enumerates each case). No GDAL/network. `tools/` items (#50 provider,
#51 fetch, #52, #54, #55) are non-offline / view-layer; their closeout is a
smoke-run + short note (the real NWIS/PRISM numbers recorded), not a unit test —
per the Epoch 8/10 lesson that a real run must exercise the paths fakes skip.

- `tests/test_flow_metrics.py` — #48/#49/#53.
- `tests/test_flow_metrics.py` — also covers #50/#51 pure validation metrics
  (merged from the former `test_flow_validation.py`).
- `web/`: extend `tests/test_recipe_roundtrip.cjs`-style headless coverage for any
  new `hydro-ux.js` report helper.

## Out of scope (deferred)

- Live `build.py` report generation (analytics live in `tools/`/notebook).
- Model gauge-calibration, NWM/Option A, NHDPlus-V2↔HR crosswalk.
- Multi-watershed comparison dashboard (follow-on).
