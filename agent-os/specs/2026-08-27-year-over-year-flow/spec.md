# Spec — Year-over-year historical flow (roadmap #44–#47, Option C)

## Overview

Today's year-in-motion render drives its twelve frames from the NHDPlus HR GDB's
long-term **climate normals** (`NHDPlusIncrPrecipMM01..12` / `TempMM01..12`) —
one *synthetic* "average year" with no calendar year attached and no history.
This epoch adds a **year-over-year axis**: run the same, already-shared
disaggregation (`src.monthly_flow.disaggregate_monthly`) against **real per-year
monthly climate from PRISM** (monthly record begins Jan 1895), for a chosen
historical year or a span of years, across CA / WA / OR / UT / ID.

Follows the **Option C** decision (see the research thread): reuse the existing
rainfall-runoff engine and swap only the climate input, so we get the deepest
history (back to 1895) for the least new architecture — no NHDPlus-V2↔HR
crosswalk and no cloud-scale NWM reads. It is honestly a *model*, not observed
gauge flow.

Mirrors the #23/#25 precedent: **promote a pure, offline algorithm + an option
surface into `src/`; keep the heavy GDAL/raster reads in a `tools/` executor
behind an injectable seam.** The default synthetic-year render stays
byte-identical.

## `src/historical_flow.py` (new, numpy-only, offline) — item #44 · **shipped in this planning commit**

```python
PRISM_FIRST_YEAR = 1895                     # PRISM monthly record start

class HistoricalFlowError(ValueError): ...  # boundary failures, fail fast

@dataclass(frozen=True)
class YearlyClimate:                        # one calendar year, [n,12] precip/temp
    year: int; precip_mm: np.ndarray; temp_c: np.ndarray
    # __post_init__ validates [n,12] + matching shapes; .reach_count -> n

@runtime_checkable
class ClimateProvider(Protocol):            # injectable seam
    def climate_for_year(self, year: int) -> YearlyClimate: ...

def normalize_years(years, *, latest=None) -> tuple[int, ...]:
    """dedup + sort; each year int, >= PRISM_FIRST_YEAR, <= latest (if given);
    empty / non-int / out-of-range -> HistoricalFlowError."""

def year_span(start, end) -> tuple[int, ...]:      # inclusive; reversed -> raise

def yearly_flow_series(provider, years, *, q_incr, hydroseq, dnhydroseq,
                       latest=None) -> dict[int, np.ndarray]:
    """For each validated year: pull climate from the provider (once per distinct
    year), run disaggregate_monthly against the fixed network -> {year: [n,12]}.
    reach-count mismatch -> HistoricalFlowError."""

def annual_mean_series(series) -> dict[int, np.ndarray]   # {year: [n]} yearly mean
def peak_month_series(series) -> dict[int, np.ndarray]    # {year: [n]} 1-based argmax
```

Pure function of its inputs — **no `datetime.now`/clock** (the newest available
year is passed in as `latest` by the caller, which knows what PRISM years it has
staged), so identical `(provider, years, network)` → identical flow. Imports only
numpy + `src.monthly_flow`; no GDAL. `__all__` exports all of the above.

## `tools/historical_flow.py` (new, non-offline) — item #45

- `PrismClimateProvider(prism_root, ...)` implements `ClimateProvider`: for a
  given year, read the 12 PRISM monthly **precip** + **tmean** grids (BIL/GeoTIFF,
  ~4 km, `.../ppt/<year>/...` and `.../tmean/<year>/...`), sample each catchment
  (zonal mean or catchment-centroid point) in the shared source CRS, and return a
  `YearlyClimate` aligned to the reach order the caller passes — the same
  `NHDPlusID`/`HydroSeq` ordering `tools/monthly_flow.build_monthly_flow` uses.
- PRISM archive is **NAS-staged** like the GDBs (see `feedback_large_file_storage`
  / `reference_nas_mount`): a few GB of monthly rasters per state cohort, HTTP-
  downloadable, no cloud compute. A small download/stage helper mirrors the
  existing cache discipline.
- Eager GIS imports live here only; `src/` and the offline suite stay GDAL-free.

## Year-over-year rendering — item #46

- Extend `tools/render_infographic_year.py` / `tools/render_monthly.py` to source
  frames from `yearly_flow_series` for **(a)** a single chosen historical year
  (the existing 12-month animation, but for e.g. 1977's drought vs. 2017's wet
  year) and **(b)** a walk *across* years (one frame per year, or interpolated).
- **Fixed cross-series width span:** compute the log flow→width mapping **once**
  across every month of every rendered year (reusing `src.rendering`'s
  `fixed_flow_span`/`widths_on_span`), so inter-year swell/drought is actually
  visible — per-year renormalization would hide it, exactly the trap `#25`
  already documents for months.

## Region expansion — item #47

- Add **Utah** to the CA/WA/OR/ID cohort (Utah is not in `SUPPORTED_REGIONS`):
  `tools/derive_state_huc4.py` → UT HUC4s, wire `SUPPORTED_REGIONS`,
  `datasets.REGION_HUC4`, `counties.STATE_FIPS`, and the `render_common.STATE_HUC4`
  mirror; download UT NHDPlus HR GDBs. This is the well-trodden Idaho path (#21's
  fourth-region precedent).

## Config / CLI surface (deferred wiring, honest caveat)

Following #25's pattern for `--months`, a future `--years` option validates via
`normalize_years` and, in the **2D pipeline**, fails fast with a message pointing
at `tools/historical_flow.py` (the DEM/monthly subsystems are not wired into
`PIPELINE_STAGES`). Not required for this epoch's gate; the engine + tool land
first.

## Determinism & byte-identical default

- No `--years` requested → nothing changes → default synthetic-year render
  byte-identical.
- Every new `src/` function is pure; identical PRISM inputs → identical flow →
  identical frames (given identical `resvg`/rasterization, per the existing tools).

## Testing (offline)

`tests/test_historical_flow.py` (**shipped, 17 passing**), injecting a fake
`ClimateProvider` + hand-built arrays over a 3-reach chain:

- `PRISM_FIRST_YEAR == 1895`; the fake satisfies the `ClimateProvider` protocol.
- `normalize_years`: dedup+sort; rejects pre-1895 / after-`latest` / empty /
  non-int / bool.
- `year_span`: inclusive ascending; rejects reversed.
- `YearlyClimate`: rejects non-`[n,12]` and mismatched precip/temp shapes.
- `yearly_flow_series`: parity with a direct `disaggregate_monthly` call; provider
  called once per distinct year; reach-count mismatch raises; a July-spike year
  peaks in July; `annual_mean_series`/`peak_month_series` shapes + mass
  conservation (mouth accumulates all upstream increments).

`tools/` items (#45–#47) are non-offline; their closeout is a smoke-render +
short validation note against real PRISM years for the five states, not a unit
test.

## Out of scope (deferred)

- Live `build.py --years` in the 2D pipeline (fails fast, like `--months`).
- Web control-surface year-over-year option (a later UX item over `hydro-ux.js`).
- Observed-gauge (USGS NWIS) calibration/validation and the NWM-retrospective
  route (Option A) — a separate, larger effort if real *observed* flow is later
  wanted.
