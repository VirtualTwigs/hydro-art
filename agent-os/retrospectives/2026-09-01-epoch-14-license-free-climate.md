# Retrospective — Epoch 14: License-free climate source (#60)

_Closed 2026-09-01. Graded against the pre-registered watch-list in
`agent-os/specs/2026-09-01-license-free-climate/planning/pre-analysis.md` (written
before implementation, per the Epoch 8/9/12 practice)._

## What the epoch was

Retire the PRISM commercial-use **Rights gate** — the block on selling any
PRISM-derived year-over-year animation or watershed report — by swapping the climate
dependency from PRISM (not public domain) to **NOAA NCEI nClimGrid-Monthly** (U.S.
federal public domain, free to sell with attribution). Mirrors the #45 precedent: the
climate source is already an injectable `ClimateProvider` seam, so only a new `tools/`
provider + fetch script + a thin pure `src/` sampling module change; the offline
engine and default synthetic-year render stay byte-identical. Hard invariant held.

## What shipped

See `implementation/report.md`. In brief: pure `src/climate_grid.py` (9 tests),
`tools/nclimgrid_flow.NClimGridClimateProvider` (drop-in for the PRISM provider),
`tools/nclimgrid_fetch.py` (stages two NetCDFs with a Content-Length check),
`--climate-source {nclimgrid,prism}` (default nclimgrid) through one factory, PRISM
gate retired in the roadmap Notes.

## Grading the watch-list

1. **Rights is the whole point — verify nClimGrid is free to sell.** *Graded — held.*
   NOAA NCEI nClimGrid is U.S. federal public domain; recorded the attribution line
   *"Climate data: NOAA NCEI nClimGrid-Monthly (public domain)."* Gate retired only
   after the terms + the real smoke were in hand, not on assumption.
2. **Band off-by-one — the highest-risk correctness bug.** *Graded — the headline
   win.* The band math was isolated in pure `src/climate_grid.band_for_month` with
   unit tests pinning the epoch boundaries (Jan 1895→1, Dec 1895→12, Jan 1896→13, Dec
   2023→1548). The real cross-check clinched it: nClimGrid Dec-2017 precip vs PRISM
   agreed to **0.6%** (254.4 vs 255.8 mm), and the seasonal contrast (Dec 254 mm ≫ Jul
   14 mm) is crisp — an off-by-one on year or month would have scrambled both. This is
   the epoch's most important evidence.
3. **Offline coverage vs "tests never import `tools/`".** *Held.* The sampling math
   lives in numpy-only `src/climate_grid.py` (offline-tested); the rasterio read lives
   in `tools/nclimgrid_flow.py` and lazy-imports rasterio (verified: `rasterio` absent
   from `sys.modules` after importing the module). The suite imports no `tools/`.
4. **"No `src/` change beyond docs" vs adding `src/climate_grid.py`.** *Graded —
   flagged honestly.* A **new** pure module landed. The roadmap promise's intent
   (engine + default render byte-identical) held: no `src.historical_flow` /
   `src.monthly_flow` / `PIPELINE_STAGES` edit, 666-test suite green. Recorded the
   nuance in the report rather than pretending no `src/` file was added.
5. **CRS/units match PRISM.** *Held.* Confirmed from real reads: precip in mm (0.6%
   agreement with PRISM's mm grid), tavg physical in °C (Jan 0.3 / Jul 17.0), grid
   EPSG:4326 vs PRISM's 4269 — sub-cell at 5 km, so no reprojection. GDAL reports
   `crs=None` on the NetCDF (no CRS tag), so the provider warns rather than crashes and
   samples lon/lat directly; the A/B agreement validates that this is safe here.
6. **Fetch volume & staging.** *Held — and caught a real bug.* `prcp` 1.47 GB + `tavg`
   1.06 GB on the NAS, 1579 bands each. The first `tavg` pull silently truncated (392
   MB, failed to open); the pre-registered risk meant the smoke checked integrity, and
   the fix (a Content-Length check in `fetch_var`) now refuses a short read.
7. **Offline fakes can't verify the real read path.** *Held.* The real read was
   exercised on 205,882 Salmon Creek reaches with both providers; real numbers
   recorded (hit-count 205,876/205,882, A/B ratios, physical magnitudes) — not stood
   in for by offline-green.
8. **Provider-selection scope-creep.** *Held.* Exactly one call site (`_make_provider`)
   constructs a provider; both share `(root, lon, lat)` + `climate_for_year`; the
   `--climate-source` flag threads through `render_state_yoy` / `report_common` /
   `build_watershed_report` without any downstream flow/render branch on source.

## What went well

- **Pre-registered risks paid off twice.** Risk #6 (staging integrity) is exactly why
  the smoke verified the file opened — catching the silent `tavg` truncation before it
  reached a render. Risk #2 (band off-by-one) drove isolating the math into a tested
  pure function *and* demanding a real cross-check, which the 0.6% PRISM agreement
  then satisfied.
- **The seam precedent held.** No new I/O shape was invented — `NClimGridClimateProvider`
  is a same-signature sibling of `PrismClimateProvider`, and the offline
  `yearly_flow_series` engine was reused verbatim. The A/B on identical reaches was
  only possible *because* both providers share the seam.

## Gotchas found

- **nClimGrid NetCDF carries no CRS tag via GDAL** (`crs=None`); it is lat/lon
  (EPSG:4326) per NOAA docs. The provider must not assume a CRS from the file — it
  samples lon/lat against the geotransform directly, validated by the PRISM A/B.
- **A dropped HTTP stream stages a truncated file with no exception.** Any large-file
  fetch to the NAS needs an explicit size check (now in `nclimgrid_fetch.py`); the
  PRISM fetcher's per-month zips were small enough to dodge this, but whole-record
  NetCDFs are not.
- **Record extends past the requested years** — `prcp`/`tavg` carry 1579 bands (through
  Jul 2026), so `latest` still governs the render window; the extra bands are simply
  never addressed.

## Carry-forward

- The animated premium tier is now **commercially clear at $0** on the default
  `--climate-source nclimgrid` path (public domain + attribution). Any
  `--climate-source prism` render remains **non-sellable** — keep that guard in mind if
  a sellable-asset pipeline ever consumes these renders.
- gridMET / Daymet remain unbuilt fallbacks if a finer-resolution or daily climate
  source is ever needed; the `ClimateProvider` seam + `src/climate_grid` helpers make
  either a same-shape addition.
- Byte-identical **full** `build.py` render compare still needs a GDAL host (shared
  carry-forward since Epoch 9/10); this epoch's invariant is satisfied structurally
  (no `PIPELINE_STAGES` code touched).
