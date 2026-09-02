# Spec — License-free climate source (Epoch 14 #60)

Retire the PRISM commercial-use Rights gate by swapping the year-over-year climate
dependency from PRISM to **NOAA nClimGrid-Monthly** (federal public domain), behind
the existing injectable `ClimateProvider` seam. The offline engine and default
render stay byte-identical; only a new `tools/` provider + fetch script + a thin
pure `src/` sampling module are added, plus a one-flag provider swap in the render
path.

See `planning/requirements.md` for the problem framing and `planning/pre-analysis.md`
for the pre-registered risk watch-list.

## Architecture (mirrors #44/#45)

```
                 (offline, unchanged, byte-identical)
  src.historical_flow.yearly_flow_series  ── ClimateProvider seam ──┐
  src.monthly_flow.disaggregate_monthly                            │
                                                                   │
  NEW  src/climate_grid.py  (pure, numpy-only, offline-tested)     │
       band_for_month() · fill_nodata() · cells_from_lonlat()      │
                        ▲ used by                                   │
                        │                                           ▼
  NEW  tools/nclimgrid_flow.py                     tools/historical_flow.py
       NClimGridClimateProvider(root,lon,lat) ─────  PrismClimateProvider(root,lon,lat)
       (lazy rasterio; NetCDF band read)             (rasterio; GeoTIFF-per-month)
                        ▲ constructed by a factory keyed on --climate-source
                        │
  render_state_yoy.yearly_flow_by_id  →  report_common  →  build_watershed_report
       (--climate-source {nclimgrid,prism}, default nclimgrid)

  NEW  tools/nclimgrid_fetch.py  → stages <root>/nclimgrid/{prcp,tavg}.nc  (NAS)
```

## Components

### 1. `src/climate_grid.py` (new, pure, numpy-only, offline)

Source-agnostic gridded-climate sampling helpers — the pure logic the nClimGrid
provider needs, factored into `src/` so it is offline-testable under the "tests
never import `tools/`" rule. Numpy-only; no rasterio, no I/O.

- `GRIDDED_FIRST_YEAR = 1895` — nClimGrid's monthly record origin (== PRISM's).
- `class ClimateGridError(ValueError)` — boundary type (mirrors `HistoricalFlowError`).
- `band_for_month(year, month, *, first_year=GRIDDED_FIRST_YEAR, one_based=True) -> int`
  — the monthly-time-axis band index: `(year-first_year)*12 + (month-1)` then `+1`
  when `one_based` (rasterio bands are 1-based). Fail fast (`ClimateGridError`) on a
  year before `first_year`, a month outside `1..12`, or a non-int.
- `cells_from_lonlat(lon, lat, inv_transform, width, height) -> (rows, cols)` —
  vectorized (col,row) from an affine inverse `(a,b,c,d,e,f)` with `np.floor` +
  `np.clip` to the grid, matching the PRISM provider's math. `lon`/`lat` must be
  matching 1-D arrays (else `ClimateGridError`).
- `fill_nodata(values, *, nodata, fill) -> np.ndarray` — replace `== nodata` and
  non-finite with `fill` (the honest ocean/nodata handling). Pure; returns a new
  array, never mutates.

`tests/test_climate_grid.py` covers all four (see tasks).

### 2. `tools/nclimgrid_flow.py` (new, non-offline)

`NClimGridClimateProvider(root, lon, lat, *, prcp_var="prcp", tavg_var="tavg")` —
implements `src.historical_flow.ClimateProvider`, same constructor shape as
`PrismClimateProvider`.

- **rasterio is lazy-imported inside the reader**, not at module top, so the module
  imports GDAL-free (the concrete band read is the only rasterio touch).
- Opens the staged NetCDF via GDAL's NETCDF driver
  (`netcdf:<root>/nclimgrid/prcp.nc:prcp`); (row,col) for every reach computed once
  via `src.climate_grid.cells_from_lonlat` from the file's inverse transform.
- `climate_for_year(year)`: for each of 12 months, band =
  `src.climate_grid.band_for_month(year, m)`, read that band, sample at
  (rows,cols), `fill_nodata(..., nodata=ds.nodata, fill=PPT_FILL|TAVG_FILL)` →
  assemble `[n,12]` → `YearlyClimate`. `PPT_FILL=0.0`, `TAVG_FILL=10.0` (matches
  `monthly_flow`/PRISM).
- Reads units + CRS from the file tags on first open and asserts mm / °C (records a
  warning, not a crash, if tags are absent) — watch-list item 5.

An **injectable `reader` seam** (default = the rasterio-backed one) lets a future
offline test exercise the orchestration with a fake; the pure math is already in
`src/climate_grid.py`.

### 3. `tools/nclimgrid_fetch.py` (new, non-offline)

Mirror of `prism_fetch.py`. Downloads the two monthly NetCDFs from a documented
public endpoint (NCEI HTTPS `…/data/nclimgrid-monthly/access/nclimgrid_<var>.nc`,
Azure NODD blob as fallback), stages `<root>/nclimgrid/<var>.nc`. Idempotent (skip
non-empty existing), atomic `.part`→final rename, mount-aware `--root`, prints
staged path + size. `--vars prcp tavg` default.

### 4. Provider selection (edit, behavior-preserving default)

`render_state_yoy.yearly_flow_by_id(..., climate_source="nclimgrid")` gains a small
factory:

```python
def _make_provider(source, root, lon, lat):
    if source == "nclimgrid":
        from tools.nclimgrid_flow import NClimGridClimateProvider
        return NClimGridClimateProvider(root, lon, lat)
    if source == "prism":
        from tools.historical_flow import PrismClimateProvider
        return PrismClimateProvider(root, lon, lat)
    raise SystemExit(f"unknown --climate-source {source!r}")
```

`render_state_yoy.main` adds `--climate-source {nclimgrid,prism}` (default
`nclimgrid`); `report_common.build_watershed_series` + `build_watershed_report.py`
thread the same argument through to `yearly_flow_by_id`. Exactly one call site
constructs a provider.

## Determinism & invariants

- `src/climate_grid.py` is numpy-only and pure (identical inputs → identical
  outputs, no mutation) — same contract as `flow_metrics`/`monthly_flow`.
- No edit to `src.historical_flow`, `src.monthly_flow`, or any `PIPELINE_STAGES`
  stage → the 2D default output and the default synthetic-year render stay
  byte-identical. The only `src/` delta is the *new* `climate_grid.py` module.
- `tests/` never imports `tools/`; the offline suite stays GDAL/network-free.

## Rights (the deliverable)

On landing + the real smoke: **retire the PRISM Rights gate** in
`agent-os/product/roadmap.md` Notes (nClimGrid is federal public domain, free to
sell with attribution — record the NOAA/NCEI attribution line). PRISM stays
reachable via `--climate-source prism` for A/B comparison; its docs note nClimGrid
is now the default license-free path.

## Acceptance

- `tests/test_climate_grid.py` green; full offline suite green (no regressions).
- `tools/nclimgrid_fetch.py` stages both NetCDFs to the NAS (real smoke; sizes
  recorded).
- `NClimGridClimateProvider` samples a real basin for ≥2 years; per-year reach
  hit-count + a wet-vs-dry width delta recorded; magnitude sanity-checked vs PRISM
  for one month.
- `render_state_yoy --climate-source nclimgrid` renders a year-over-year frame set
  from real nClimGrid data.
- PRISM Rights gate retired in the roadmap Notes; CLAUDE.md/HANDOFF swept; roadmap
  #60 ticked; Epoch 14 retrospective written and graded against the watch-list.
