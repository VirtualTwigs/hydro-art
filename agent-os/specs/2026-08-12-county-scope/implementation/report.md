# Implementation Report — County scope in the pipeline (roadmap #24)

## Summary

Promoted `tools/render_county_clip.py`'s county clip into a first-class
`--county` build option. A build can now target a single Census county within
the selected state; `clip_to_region` clips the hydrography (and the
`region_boundary` artifact waterbody selection reuses) to that county's polygon
instead of the WBD region boundary. Default (`county` unset) is byte-identical.

## Changes

- **`src/config.py`** — new `county: str | None` field + `DEFAULTS["county"] =
  None`. `build_settings` strips the value (empty/whitespace → `None`) and, when
  set, requires exactly one region (else `ConfigError`). Every supported region
  already maps to a Census FIPS, so no new allowlist was needed.
- **`src/cli.py`** — new `--county` flag (default `None`) mapped to the flat
  `county` override key; the existing shallow merge and `defaults < YAML < CLI`
  precedence apply unchanged.
- **`src/counties.py`** (new) — the county-boundary seam:
  - `STATE_FIPS` (Oregon 41 / Washington 53 / California 06), kept in sync with
    `SUPPORTED_REGIONS` (asserted by a test).
  - `state_fips_for_region` (pure; `ConfigError` if unmapped) and
    `county_boundary(provider, region, county, target_crs)` (resolves FIPS then
    delegates to the injected provider).
  - `CountyBoundaryProvider` protocol + `CensusCountyProvider` default, which
    lazy-imports geopandas, reads the Census counties shapefile, filters
    `STATEFP`+`NAME` (case-insensitive), and reprojects to `target_crs`. Missing
    shapefile / missing county → `AcquisitionError` with an actionable message.
    `src/` stays GDAL-free at import time (heavy GIS lazy-imported behind the
    seam); `src/` does not import `tools/` (shapefile path redeclared here).
- **`src/pipeline.py`** — `RunContext`/`Pipeline` gain an injectable
  `county_provider`. `_clip_stage` branches on `settings.county`: county set →
  `county_boundary(...)` at `settings.projection`; else `region_boundary(layers)`
  as before. The chosen boundary is stored in `artifacts["region_boundary"]`.
  `_export_stage` appends the county slug to the filename stem (e.g.
  `oregon-hood-river.svg`); unset → unchanged stem.

## Tests

- `tests/test_config.py` (+4): default `None`, single-region accept + strip,
  empty → `None`, multi-region + county → `ConfigError`.
- `tests/test_cli.py` (+3): `--county` override, YAML survival when unset,
  CLI-over-YAML precedence.
- `tests/test_counties.py` (new, 6): FIPS per region, full `SUPPORTED_REGIONS`
  coverage, unknown region raises, delegation with resolved FIPS+CRS, not-found
  propagation, default provider surfaces a missing-shapefile error offline.
- `tests/test_county_pipeline.py` (new, 3): county clip keeps only in-county
  geometry and sets the county boundary artifact; export filename named after
  the county; default build still clips to the WBD region and keeps its filename.

## Verification

- Full suite: **310 passed** (was 276; +34 across this item and prior additions),
  fully offline (no GDAL, no network). Pre-existing "svgo not found" warnings
  only.
- Smoke: `build_settings({"region":["Oregon"],"county":"Multnomah"})` carries the
  county; a county-scoped run clips against a fake provider on hand-built layers
  without error; `county_boundary` resolves `California` → FIPS `06`.
- Note: `ruff` is not installed in this `.venv`, so the lint pass was skipped;
  code follows the module's existing style (annotations import, docstrings,
  `__all__`).

## Out of scope (as specced)

- Download scoping by county HUC4 (still fetches the whole state, then clips).
- County outline overlay / legend / rasterize (remain tool-only).
- `--months` (#25) and the web control surface (#26).
