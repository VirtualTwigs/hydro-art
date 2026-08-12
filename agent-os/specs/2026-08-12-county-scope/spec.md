# Spec — County scope in the pipeline (roadmap #24)

## Overview

Add a `county` build option that clips the pipeline's output to a single Census
county polygon within the selected state. Loading the polygon goes through a new
injectable seam (`src/counties.py`) so the offline suite stays GDAL-free. Default
(`county` unset) keeps existing builds byte-identical.

## Config (`src/config.py`)

New `Settings` field + `DEFAULTS` entry:

| field    | type         | default | validation                                            |
|----------|--------------|---------|-------------------------------------------------------|
| `county` | `str \| None`| `None`  | if set → exactly one `region`; region is a supported state |

`build_settings`:

- `county = values.get("county")`; empty string / whitespace normalizes to
  `None` (treated as unset).
- If `county` is set and `len(regions) != 1`, raise `ConfigError` ("a county
  build must target exactly one state; got regions=…").
- The single region is already normalized/validated against `SUPPORTED_REGIONS`;
  every supported region has a Census FIPS (see `src/counties.STATE_FIPS`), so no
  extra allowlist is needed here. Store the stripped county string.

No new allowlist constant. County *existence* in the dataset is verified at clip
time (needs the shapefile), not at config time — mirroring how region→HUC4
existence is checked during acquisition, not in `build_settings`.

## CLI (`src/cli.py`)

- New flag `--county` (default `None`), mapped in `cli_overrides` to the flat
  top-level key `county`. The existing shallow `merge_values` suffices.

## County boundary seam (`src/counties.py`, new)

Pure, import-light module (heavy GIS lazy-imported inside the provider only):

```python
STATE_FIPS: dict[str, str] = {"Oregon": "41", "Washington": "53", "California": "06"}

DEFAULT_COUNTY_SHAPEFILE = "/tmp/counties_shp/cb_2023_us_county_500k.shp"

class CountyBoundaryProvider(Protocol):
    def load(self, *, state_fips: str, county: str, target_crs: str) -> Any: ...

def state_fips_for_region(region: str) -> str:
    """Census STATEFP for a supported region; ConfigError if unmapped."""

def county_boundary(provider, region, county, target_crs) -> Any:
    """Resolve region→FIPS (pure) then delegate to provider.load (I/O)."""

class CensusCountyProvider:
    """Default provider: lazy-imports geopandas, reads the Census counties
    shapefile, filters STATEFP + NAME (case-insensitive), reprojects to
    target_crs. Missing county → AcquisitionError. Mirrors
    tools/render_common.load_county but lives in src/ (tools must not be imported
    by src/)."""
```

`STATE_FIPS` is kept in sync with `SUPPORTED_REGIONS` (a test asserts every
supported region has a FIPS). `AcquisitionError` is imported from `src.datasets`
(no cycle: `datasets` does not import `counties`).

## Pipeline wiring (`src/pipeline.py`)

- `RunContext` gains `county_provider: CountyBoundaryProvider | None = None`
  (defaulted; `artifacts` stays last).
- `Pipeline.__init__`/`run` accept + inject a `county_provider`, defaulting to
  `CensusCountyProvider()` (constructed lazily in `run`, like the other
  collaborators).
- `_clip_stage`: if `ctx.settings.county` is set, compute the boundary via
  `county_boundary(provider, region, county, target_crs=ctx.settings.projection)`
  (provider = `ctx.county_provider or CensusCountyProvider()`); otherwise
  `region_boundary(layers)` as today. The resulting boundary is clipped against
  and stored in `artifacts["region_boundary"]` (so waterbody selection reuses the
  county boundary). Log line notes the county when scoped.
- `_export_stage`: the filename stem includes the county when set — e.g.
  `f"{region_stem}-{county_slug}"` where `county_slug` lowercases and replaces
  whitespace with `-`. Unset → unchanged stem (byte-identical filename).

## Determinism & byte-identical default

- `county is None` → `_clip_stage` and `_export_stage` take exactly their current
  paths; SVG bytes and filename unchanged.
- `state_fips_for_region` / `county_boundary` are pure; the provider is the only
  I/O and is injected.

## Testing (offline)

- Config: default `county is None`; valid single-region county accepted;
  multi-region + county → `ConfigError`; empty string → `None`.
- CLI: `--county` maps to override; unset produces no key; precedence holds.
- `counties.py`: `state_fips_for_region` returns FIPS / raises on unknown; every
  `SUPPORTED_REGION` has a FIPS; `county_boundary` delegates to an injected fake
  provider with the resolved FIPS + target CRS; a fake "not found" provider
  raises `AcquisitionError`.
- Pipeline: with `county` set and an injected fake provider returning a
  hand-built shapely polygon, the clip uses the county boundary (only inside
  geometry survives) and the export filename includes the county; default build
  still clips to the WBD boundary (regression guard).

## Out of scope (deferred)

- Download scoping by county HUC4 (still fetches the whole state).
- County outline overlay / legend / rasterize (tool-only).
- `--months` (#25) and web control surface (#26).
