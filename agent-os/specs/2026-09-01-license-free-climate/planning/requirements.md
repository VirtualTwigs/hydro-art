# Requirements — License-free climate source (Epoch 14 #60)

## The problem

The year-over-year animation (#45/#46) and the watershed reports (#48–#55) are the
project's most striking output but are **commercially blocked**: PRISM data is not
public domain. PRISM's terms prohibit commercial use "unless you have made special
arrangements in advance" — an unpriced custom quote — and prohibit redistribution
even on the paid 800 m tier. The free 4 km tier this project samples
(`tools/prism_fetch.py`) carries the same commercial prohibition. Every
PRISM-derived asset is therefore parked behind the roadmap **Rights gate**.

## The fix

Swap the climate dependency for a **U.S.-government / free-for-any-use gridded
alternative** so the animated premium tier unlocks for **$0 licensing** and the
PRISM Rights gate is **retired entirely**.

- **Chosen source: NOAA nClimGrid-Monthly** — federal public domain, the direct
  PRISM equivalent: monthly `prcp` (mm) + `tavg` (°C), ~5 km (1/24°) grid, CONUS,
  record from **January 1895** to present. Distributed as **two big NetCDF files**
  (`nclimgrid_prcp.nc`, `nclimgrid_tavg.nc`), each with a monthly `time` dimension —
  GDAL/rasterio exposes each month as a **band**. Free to sell with attribution.
- Fallbacks (not implemented now, recorded for the retro): **gridMET** (U. Idaho,
  4 km daily, commercial-OK) and **Daymet** (ORNL/NASA, 1 km daily).

## Why this is a small change

The climate source is already an **injectable `ClimateProvider` seam**
(`src/historical_flow.py`, #44). The real PRISM impl
(`tools/historical_flow.PrismClimateProvider`) is one class behind that seam. So
only a **new `tools/` provider impl + a fetch/stage script** are added; the offline
`src.historical_flow.yearly_flow_series` engine and every downstream render
(`render_state_yoy.py`, `report_common.py`, the report builder) stay untouched and
**byte-identical**. This mirrors the #45 precedent exactly.

## Functional requirements

1. **Fetch/stage tool** `tools/nclimgrid_fetch.py` (the nClimGrid counterpart to
   `prism_fetch.py`): download the two monthly NetCDF files from a documented
   public NOAA/NCEI (or NODD/Azure) endpoint, stage under
   `<root>/nclimgrid/<var>.nc` on the NAS external root. Idempotent/resumable
   (skip a file already staged with non-zero size; atomic `.part`→final rename),
   mount-aware, polite. Prints staged path + byte size per file.
2. **Provider** `tools/nclimgrid_flow.NClimGridClimateProvider(root, lon, lat)`:
   implements `src.historical_flow.ClimateProvider` — samples the staged NetCDF at
   each catchment centroid → `YearlyClimate(year, precip_mm[n,12], temp_c[n,12])`,
   in the caller's exact reach order. Same constructor shape as
   `PrismClimateProvider` so it's a drop-in.
   - (row, col) of every reach computed **once** from the shared geotransform, then
     vectorized across all months/years (mirrors PRISM provider).
   - Monthly band index derived from `(year, month)` and the record's first year
     (1895): `band = (year - 1895) * 12 + (month - 1)` (0-based) / `+1` (rasterio
     1-based). Off-by-one here is the highest-risk bug — must be unit-tested.
   - **Honest nodata handling** identical to `tools/monthly_flow.py` /
     `PrismClimateProvider`: ocean/nodata → precip `0.0` mm, temp `10.0 °C`
     (mild, no snow). Never invent data.
   - Units already match PRISM (mm, °C); nClimGrid CRS is EPSG:4326 (WGS84) vs
     PRISM's EPSG:4269 (NAD83) — the datum offset is sub-cell at 5 km, so reach
     lon/lat sample directly with no reprojection.
3. **Selectable source** in the render/report path: `render_state_yoy.yearly_flow_by_id`
   builds the provider via a small factory keyed by a `--climate-source
   {nclimgrid,prism}` flag (**default `nclimgrid`** — the license-free path).
   `report_common` / `build_watershed_report.py` thread the same flag. Both
   providers share the `(root, lon, lat)` constructor + `climate_for_year` seam, so
   the swap is one call site.
4. **Offline test coverage** for the new sampling math. The repo rule "the test
   suite must not import `tools/`" means the provider's *pure* logic (band-index,
   nodata fallback, lon/lat→cell) can only be tested offline if it lives in `src/`.
   Factor a thin **pure, numpy-only `src/climate_grid.py`** for that logic (mirrors
   the `src/monthly_flow.py` ↔ `tools/monthly_flow.py` split); the rasterio I/O
   stays in `tools/nclimgrid_flow.py` and lazy-imports rasterio so the module is
   GDAL-free at import. `tests/test_climate_grid.py` covers it.

## Non-functional / invariants (grade in the retro)

- **Offline-suite discipline preserved.** `src/` + `tests/` never import GDAL /
  rasterio / `tools/` at module top level; the new `src/climate_grid.py` is
  numpy-only. Full offline suite stays green.
- **Engine + default render byte-identical.** No change to
  `src.historical_flow`, `src.monthly_flow`, or any `PIPELINE_STAGES` code; the
  default synthetic-year render is unaffected. `src/climate_grid.py` is a *new*
  module, not an edit to the engine.
- **Reproducibility.** nClimGrid NetCDFs are staged + recorded (path + size) the
  same way PRISM grids are; a render rebuilds offline from the staged files.
- **Rights.** On landing, **retire the PRISM Rights gate** in
  `agent-os/product/roadmap.md` Notes and stamp the nClimGrid attribution line for
  sold assets.

## Out of scope

- gridMET / Daymet providers (fallbacks only; recorded, not built).
- Re-staging or deleting the existing PRISM catalog (leave staged PRISM as-is;
  PRISM provider stays available behind `--climate-source prism` for comparison).
- Any change to the 2D pipeline, the synthetic-year `monthly_flow` render, or the
  web surface.
