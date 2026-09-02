# Tasks — License-free climate source (Epoch 14 #60)

Legend: `[x]` done · `[ ]` todo. Offline items ship **tests-first** (write 2–8 tests
per group, run ONLY those, then implement). `tools/` items are non-offline
(closeout = smoke-run + record real numbers). Grade against
`planning/pre-analysis.md` at close.

## Group 1 — Pure gridded-sampling helpers (`src/climate_grid.py`) · offline

- [x] 1.1 Write `tests/test_climate_grid.py` first, with known answers:
  - `band_for_month`: Jan 1895 → 1; Dec 1895 → 12; Jan 1896 → 13; Dec 2023 →
    `(2023-1895)*12+12 = 1548`. `one_based=False` shifts each by −1. Off-by-one is
    watch-list risk #2, so pin the epoch boundaries explicitly.
  - `band_for_month` guards: year < 1895 → `ClimateGridError`; month 0 or 13 →
    `ClimateGridError`; bool/non-int year → `ClimateGridError`.
  - `cells_from_lonlat`: a hand-built inverse-affine over a small grid → expected
    (rows, cols); points outside the grid clip to the edge; mismatched/2-D lon/lat →
    `ClimateGridError`.
  - `fill_nodata`: an array with the sentinel and a NaN → both become `fill`; finite
    values untouched; input array not mutated (purity).
- [x] 1.2 Implement `src/climate_grid.py` (numpy-only; `__all__`; `from __future__
  import annotations`; frozen boundary type `ClimateGridError(ValueError)`).
- [x] 1.3 Run only `tests/test_climate_grid.py`. **9 passed.**

## Group 2 — nClimGrid provider (`tools/nclimgrid_flow.py`) · non-offline

- [x] 2.1 `NClimGridClimateProvider(root, lon, lat)` implementing
  `src.historical_flow.ClimateProvider` — same `(root, lon, lat)` shape as
  `PrismClimateProvider`. rasterio **lazy-imported inside the reader** (module
  imports GDAL-free); (row,col) computed once via
  `src.climate_grid.cells_from_lonlat`; per-month band via
  `src.climate_grid.band_for_month`; nodata via `src.climate_grid.fill_nodata`
  (`PPT_FILL=0.0`, `TAVG_FILL=10.0`). Reads + asserts units (mm/°C) and CRS from the
  file tags (warn, don't crash, if absent).
- [x] 2.2 Confirmed via a fake-reader offline smoke: `isinstance(p,
  ClimateProvider)` True; module imports with `rasterio` absent from `sys.modules`
  (lazy import held); band-per-month correct (Jan 1896 → band 13 … Dec → 24); nodata
  cell → precip 0 / temp 10 fallback.

## Group 3 — Fetch/stage tool (`tools/nclimgrid_fetch.py`) · non-offline

- [x] 3.1 `tools/nclimgrid_fetch.py` mirroring `prism_fetch.py`: downloads
  `nclimgrid_prcp.nc` + `nclimgrid_tavg.nc` from the NCEI HTTPS access endpoint
  (verified live: prcp 1.47 GB, tavg 1.06 GB, `application/x-netcdf`) with Azure
  NODD blob fallback → `<root>/nclimgrid/nclimgrid_<var>.nc`. Idempotent skip on
  non-empty existing, streamed to `.part`→atomic rename, `--root`/`--vars`, prints
  path+size. License: **NOAA NCEI nClimGrid is U.S. federal public domain** (verify
  attribution line at 5.1).
- [x] 3.2 (smoke) Staged both NetCDFs to `/Volumes/home/data/hydro-art/nclimgrid/`:
  `nclimgrid_prcp.nc` = 1,466,321,553 b, `nclimgrid_tavg.nc` = 1,058,299,596 b; each
  opens via the GDAL NETCDF driver with **1579 bands** (Jan 1895 → Jul 2026), so
  `band_for_month(2023,12)=1548` is in range. **Caught a real bug (watch-list #6):**
  the first `tavg` pull silently truncated (392 MB, failed to open) — added a
  Content-Length check to `fetch_var` so a short read raises + retries the mirror;
  re-fetch landed the full 1.06 GB file.

## Group 4 — Provider selection wiring · non-offline

- [x] 4.1 Added `_make_provider(source, root, lon, lat)` factory + `climate_source`
  param to `render_state_yoy.yearly_flow_by_id` (default `"nclimgrid"`); added
  `--climate-source {nclimgrid,prism}` to `render_state_yoy.main`. Exactly one call
  site constructs a provider. Import verified.
- [x] 4.2 Threaded `climate_source` through `report_common.load_watershed_series`
  and `--climate-source` through `tools/build_watershed_report.py` to
  `yearly_flow_by_id`. No downstream flow/render code branches on source (verified).

## Group 5 — Real smoke + validation · non-offline (record real numbers)

- [x] 5.1 Sampled Salmon Creek's HUC4 1708 (205,882 reaches via `_yoy_net_1708.pkl`)
  with **both** providers on identical `(lon,lat)`. **Recorded:**
  - Seasonal signal correct (band mapping): nClimGrid precip Dec-2017 mean **254 mm**
    vs Jul-2015 **14 mm**; coverage 205,876/205,882 (6 ocean → 0 fallback).
  - **A/B vs PRISM within 0.6%:** Dec-2017 precip nClimGrid 254.4 mm vs PRISM 255.8
    mm (ratio 0.994) — independent grids agreeing this tightly confirm geotransform,
    CRS (4326 vs 4269 sub-cell), band index, and units (both mm). Watch-list #2/#5/#7
    refuted.
  - Full engine (`yearly_flow_series`): 2017 peak-flow nClimGrid/PRISM ratio 0.987,
    2015 ratio 1.091. 2017 climate physical: annual precip mean 2548 mm, Jan temp 0.3
    °C / Jul 17.0 °C. (Annual wet/dry ratio ≈1.0 is *expected* — `disaggregate_monthly`
    conserves mean-annual flow; year-over-year variation is seasonal timing, not
    volume.)
- [ ] 5.2 `render_state_yoy --climate-source nclimgrid --start … --end …` renders a
  year-over-year frame set from real nClimGrid data (record frame count + that
  wet/drought years differ in channel thickness on the fixed cross-year span).

## Group 6 — Close out + post-development cleanup · offline + docs

- [x] 6.1 Full offline suite green: **666 passed** (657 + 9 new `test_climate_grid`).
  No `PIPELINE_STAGES` / `src.historical_flow` / `src.monthly_flow` edit — only the
  *new* `src/climate_grid.py` module → default render byte-identical; `tests/`
  imports no `tools/` (new test imports only `src.climate_grid`).
- [x] 6.2 **Retired the PRISM Rights gate** in `agent-os/product/roadmap.md` Notes:
  nClimGrid is U.S. federal public domain, default `--climate-source nclimgrid` is
  commercially clear at $0 with attribution *"Climate data: NOAA NCEI
  nClimGrid-Monthly (public domain)."*; PRISM stays A/B-only and never sellable.
- [x] 6.3 Docs sweep: CLAUDE.md (module map += `src/climate_grid.py`; ad-hoc tools
  += license-free climate subsection with `nclimgrid_flow.py`/`nclimgrid_fetch.py` +
  default source note); roadmap #60 ticked. `HANDOFF.md` + `implementation/report.md`
  pending.
- [ ] 6.4 Write `agent-os/retrospectives/2026-09-01-epoch-14-license-free-climate.md`
  graded against `planning/pre-analysis.md`.
