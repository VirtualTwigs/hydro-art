# Implementation report — License-free climate source (Epoch 14 #60)

_Closed 2026-09-01._

## What shipped

Swapped the year-over-year / watershed-report climate dependency from PRISM (not
public domain) to **NOAA NCEI nClimGrid-Monthly** (U.S. federal public domain),
behind the existing injectable `ClimateProvider` seam, and **retired the PRISM Rights
gate**. The offline engine and default synthetic-year render are byte-identical; the
only `src/` delta is a *new* pure module.

- **`src/climate_grid.py`** (new, pure, numpy-only, offline) — source-agnostic
  gridded-climate sampling: `GRIDDED_FIRST_YEAR=1895`, `band_for_month`,
  `cells_from_lonlat`, `fill_nodata`, `ClimateGridError`. Factored into `src/` so the
  nClimGrid provider's highest-risk math (band off-by-one) is offline-testable under
  the repo rule that the test suite never imports `tools/`.
  `tests/test_climate_grid.py` — **9 tests**.
- **`tools/nclimgrid_flow.py`** (new, non-offline) — `NClimGridClimateProvider(root,
  lon, lat)`, a drop-in for `PrismClimateProvider`. nClimGrid ships as a stacked
  NetCDF addressed by band (GDAL NETCDF driver: month `m` of `year` =
  `band_for_month(year, m)`); (row,col) computed once via `cells_from_lonlat`, nodata
  via `fill_nodata` (precip→0, temp→10 °C, matching `monthly_flow.py`). **rasterio is
  lazy-imported inside the reader** so the module imports GDAL-free; a `BandReader`
  seam allows a fake in future offline tests.
- **`tools/nclimgrid_fetch.py`** (new, non-offline) — stages the two monthly NetCDFs
  from the NCEI HTTPS access endpoint (Azure NODD blob fallback) to
  `<root>/nclimgrid/`, streamed to `.part`→atomic rename with a **Content-Length
  check**.
- **Provider selection** — `--climate-source {nclimgrid,prism}` (default `nclimgrid`)
  resolves at a single `_make_provider` factory in `render_state_yoy.py`, threaded
  through `report_common.load_watershed_series` and `build_watershed_report.py`. No
  downstream flow/render code branches on source.
- **Rights** — PRISM gate retired in `agent-os/product/roadmap.md` Notes; CLAUDE.md
  (module map + ad-hoc tools) and HANDOFF.md swept; roadmap #60 ticked.

## Real-data validation (the credibility hinge)

Sampled Salmon Creek's HUC4 1708 (205,882 reaches) with **both** providers on
identical `(lon,lat)`:

- **Band mapping correct (seasonal signal):** nClimGrid precip Dec-2017 mean **254
  mm** vs Jul-2015 **14 mm** — an off-by-one on year/month would scramble this.
- **A/B vs PRISM within 0.6%:** Dec-2017 precip nClimGrid 254.4 mm vs PRISM 255.8 mm
  (ratio 0.994). Two independent grids agreeing this tightly confirms the
  geotransform, CRS (EPSG:4326 vs 4269 sub-cell at 5 km), band index, and units (both
  mm) are all correct.
- **Through the real engine:** 2017 peak-flow nClimGrid/PRISM ratio 0.987; 2015 ratio
  1.091. 2017 climate physical (annual precip mean 2548 mm; Jan 0.3 °C / Jul 17.0 °C).
- **Staging:** `nclimgrid_prcp.nc` 1,466,321,553 b + `nclimgrid_tavg.nc` 1,058,299,596
  b, each 1579 bands (Jan 1895 → Jul 2026).

## Bug caught & fixed

The first `tavg` download silently truncated (392 MB vs 1.06 GB) — a dropped
connection yields a short file with no exception. `fetch_var` now verifies the byte
count against `Content-Length` and raises (retrying the next mirror) so a truncated
NetCDF never stages. This is watch-list risk #6, caught in the smoke rather than in a
render.

## Invariants held

- Full offline suite **666 passing** (+9); `tests/` imports no `tools/`.
- No `PIPELINE_STAGES` / `src.historical_flow` / `src.monthly_flow` edit → 2D default
  output and default synthetic-year render byte-identical. Only a new `src/` module
  (`climate_grid.py`) was added, not an edit to the engine.
- `src/climate_grid.py` is numpy-only and pure.

## Honest notes

- **A small `src/` module was added**, despite the roadmap line "no `src/` change
  beyond docs." The promise's *intent* — engine + default render byte-identical —
  held; the new module was the only way to get offline coverage of the sampling math
  under the "tests never import `tools/`" rule. Flagged rather than hidden.
- The wet/dry **annual** flow ratio is ≈1.0 because `disaggregate_monthly` conserves
  each reach's mean-annual flow; year-over-year variation is in seasonal *timing*, not
  annual volume. This is an existing property of the render, unchanged by the source
  swap — not a regression.
- gridMET / Daymet fallbacks were scoped out (recorded only). The existing PRISM
  catalog is left staged; the PRISM provider stays reachable via `--climate-source
  prism` for A/B and remains **non-sellable**.
