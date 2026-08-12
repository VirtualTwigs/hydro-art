# Task Breakdown — County scope in the pipeline (roadmap #24)

TDD: write 2–8 tests first per group, run only those, then implement until green.

## Task Group 1: Config option (`src/config.py`)

- [x] Tests (`tests/test_config.py`): default `county is None`; a single-region
  build with `county="Clark"` is accepted and stored (stripped); `county` set
  with two regions raises `ConfigError`; empty/whitespace `county` normalizes to
  `None`.
- [x] Add `county` to `DEFAULTS`, the `Settings` dataclass, and `build_settings`
  validation (single-region rule + strip-to-None).

## Task Group 2: CLI flag (`src/cli.py`)

- [x] Tests (`tests/test_cli.py`): `--county Clark` parses into the `county`
  override; unset produces no `county` key (YAML survives); precedence
  `defaults < YAML < CLI` holds for `county`.
- [x] Add `--county` to `build_parser` and map it in `cli_overrides`.

## Task Group 3: County boundary seam (`src/counties.py`)

- [x] Tests (`tests/test_counties.py`): `state_fips_for_region` returns the FIPS
  for each supported region and raises `ConfigError` on an unknown region; every
  `SUPPORTED_REGION` has a `STATE_FIPS` entry; `county_boundary` delegates to an
  injected fake provider with the resolved FIPS + `target_crs`; a fake provider
  that raises `AcquisitionError` propagates.
- [x] Implement `STATE_FIPS`, `state_fips_for_region`, `county_boundary`,
  `CountyBoundaryProvider` protocol, and `CensusCountyProvider` (lazy geopandas).

## Task Group 4: Pipeline wiring (`src/pipeline.py`)

- [x] Tests (`tests/test_county_pipeline.py`): with `county` set + an injected
  fake provider returning a hand-built polygon, the clip uses the county boundary
  (inside kept, outside dropped) and `artifacts["region_boundary"]` is the county
  polygon; the export filename stem includes the county; a default (no-county)
  run still clips to the WBD boundary.
- [x] Add `county_provider` to `RunContext` + `Pipeline`; branch `_clip_stage`
  on `settings.county`; include the county in the `_export_stage` filename stem.

## Task Group 5: Verification & docs

- [x] Write `implementation/report.md`.
- [x] Tick these checkboxes; run the full suite for regressions.
- [x] Smoke-test: `build_settings({"region": ["Oregon"], "county": "Multnomah"})`
  carries `county`; a county-scoped settings object clips against a fake provider
  on a hand-built graph without error.
- [x] Report and STOP (commit is a separate explicit step).

## Verification gates

1. Default (no `county`) build SVG + filename byte-identical to pre-change.
2. `county` with != 1 region raises `ConfigError`; unknown region FIPS raises;
   missing county raises `AcquisitionError`.
3. `src/counties.py` pure functions are deterministic and covered; heavy GIS is
   lazy-imported behind the injected provider.
4. A county-scoped build clips to the county polygon and names the file after it.
5. Full suite green; `src/` stays GDAL-free and offline.
