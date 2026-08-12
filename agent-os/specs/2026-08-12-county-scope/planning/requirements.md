# Requirements — County scope in the pipeline (roadmap #24)

## Goal

Promote `tools/render_county_clip.py`'s county clip into a first-class `--county`
build option so scope selection is a normal pipeline setting, not a separate
script. A build can target a single Census county within the selected state; the
hydrography is clipped to that county's polygon instead of the full WBD region
boundary.

## Functional requirements

1. A new `county` setting (config + `--county` CLI flag) names one U.S. county
   (Census `NAME`, e.g. `Clark`, case-insensitive).
2. `county` is **validated against the selected state**: a county build must
   select exactly one region, and that region must be a supported state (all of
   which map to a Census STATEFP). Violations fail fast with `ConfigError`.
3. When `county` is set, `clip_to_region` clips the projected hydrography (and
   the `region_boundary` artifact that waterbody selection reuses) to the Census
   county polygon rather than the union of WBD polygons.
4. County-polygon loading goes through an **injectable seam** so the offline test
   suite stays GDAL-free: a `CountyBoundaryProvider` collaborator is injected on
   the pipeline; the default `CensusCountyProvider` lazy-imports geopandas and
   reads the Census cartographic-boundary counties shapefile.
5. A county not present in the shapefile fails fast with an `AcquisitionError`
   carrying an actionable message (state FIPS + county name + shapefile path).
6. The exported filename incorporates the county so a county build doesn't
   collide with the whole-state build (e.g. `oregon-multnomah.svg`).

## Non-functional / invariants

- **Byte-identical default:** with `county` unset (the default), the clip stage
  takes exactly its current path (`region_boundary(layers)`); no output changes.
- `src/` stays offline-testable and GDAL-free: heavy GIS access is lazy-imported
  behind the new seam, like `Downloader`/`LayerLoader`.
- Config precedence unchanged: `defaults < YAML < CLI`; `--county` defaults to
  `None` so it never clobbers a YAML value.
- Deterministic: same inputs → same clipped output.
- Error taxonomy: config-shape problems → `ConfigError`; a county that can't be
  resolved from the dataset → `AcquisitionError`.

## Out of scope (deferred)

- Optimizing the download stage to fetch only the county's HUC4(s); a county
  build still acquires the whole state's HUC4 archives and clips down. (Download
  scoping is a separate optimization.)
- The county-outline overlay / legend / rasterize niceties in
  `tools/render_county_clip.py` (those stay tool-only).
- `--months` (#25) and the web control surface (#26).
