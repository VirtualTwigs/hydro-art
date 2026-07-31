# Implementation Report: DEM Elevation & 3D Modeling

## Task Group 1 — Elevation contract and configuration (roadmap item 11)

Implemented 2026-07-30, TDD-first. This is the configuration + provenance
*contract only*; no pipeline stage reads it yet (DEM acquisition is item 12), so
a default 2D build is unchanged.

### Confirmed art-direction decisions (applied here)

1. **Off by default** — `elevation.enabled = False`. Nothing in the pipeline
   reads `Settings.elevation`, so default builds stay byte-identical 2D.
2. **Preserve source vertical reference only** — `ElevationProvenance` records
   the DEM's own `vertical_crs`/`vertical_units` verbatim (including `None` when
   the source states none). There is deliberately **no** normalize-to-NAVD88
   option; that stays a later, explicit decision.
3. **Default resolution tier = `preview`** — the coarse, cheap tier. `state`/
   `local` escalate detail only when explicitly requested (no statewide 1 m
   default, per the non-functional budget constraint).

### What landed

- **`src/config.py`**
  - Allowlists: `SUPPORTED_ELEVATION_SOURCES = ("3dep",)`,
    `SUPPORTED_ELEVATION_TIERS = ("preview", "state", "local")`,
    `SUPPORTED_CACHE_POLICIES = ("reuse", "refresh")`.
  - `DEFAULTS["elevation"]` block (`enabled=False`, `source="3dep"`,
    `tier="preview"`, `vertical_exaggeration=1.0`, `cache_policy="reuse"`). Being
    a `DEFAULTS` key also means an `elevation:` YAML block no longer trips the
    "unknown config keys" warning in `load_yaml`.
  - `ElevationSettings` frozen dataclass + `_coerce_elevation` validator
    (tolerates a partial mapping like `_coerce_waterbodies`; validates the three
    allowlists and `vertical_exaggeration > 0`). New `elevation` field on
    `Settings`, wired through `build_settings`; exports updated.

- **`src/elevation.py`** (new)
  - `ElevationProvenance` immutable metadata: `source_product`, `source_url`,
    `acquisition_date`, `horizontal_crs`, `vertical_crs`, `vertical_units`,
    `resolution_m`, `checksum`, `processing_parameters`.
  - `build_provenance(...)` boundary validation: required identity fields
    (`source_product`/`source_url`/`acquisition_date`/`horizontal_crs`/`checksum`)
    non-empty, `resolution_m > 0`; vertical fields optional and preserved
    verbatim. Raises `ElevationError(AcquisitionError)` so `build.py` maps it to
    the acquisition exit code (2).
  - Value objects `TileRef` and `ElevationSample(value_m, covered, nodata)`.
  - Plain (non-`runtime_checkable`) protocols `TileDiscoverer`, `RasterReader`,
    `ElevationSampler` — the injected seams items 12/13/14 will implement with
    GDAL-backed classes while tests inject fakes. No heavy raster libs imported.

- **`src/cli.py`**
  - Flags `--elevation/--no-elevation` (BooleanOptionalAction),
    `--elevation-source`, `--elevation-tier`, `--vertical-exaggeration` (float),
    `--cache-policy`; collected under a nested `overrides["elevation"]` and
    **deep-merged** per sub-key in `resolve_settings` (mirrors the waterbodies
    precedence), so `defaults < YAML < CLI` holds per sub-key.

### Tests

- `tests/test_elevation_config.py` (10): defaults, partial-dict fill,
  invalid tier/source/cache_policy, non-positive exaggeration, YAML override,
  CLI-over-YAML per-sub-key precedence, and a guard that a default build keeps
  elevation disabled.
- `tests/test_elevation.py` (9): provenance records all fields, immutability,
  missing-required-field + non-positive-resolution rejection,
  `ElevationError ⊂ AcquisitionError`, absent vertical reference preserved as
  `None`, sample/tile value objects, and structural conformance of all three
  protocols against fakes.

### Verification

- New tests: **19 passed**.
- Full suite: **208 passed** (was 189; +19), no regressions.
- Smoke test: `resolve_settings([])` → elevation disabled/preview; flag
  combination applies tier/exaggeration/cache; invalid tier rejected with a
  user-facing `ConfigError`.
- `ruff` not installed in the offline venv; not run.

### Deferred (later task groups / gated on decisions)

Groups 3–6 (raster normalization/sampling, Z-hydrography, mesh/scene, GLB
export) remain planning-only. Groups 5–6 are blocked on the two still-open
decisions in `planning/requirements.md` (mesh/error budget, GLB-vs-OBJ). The
injected protocols added here are the seams those groups plug into.

## Task Group 2 — 3DEP discovery and cache (roadmap item 12)

Implemented 2026-07-30, TDD-first, fully offline. Delivers DEM tile discovery +
caching; no raster is opened or reprojected yet (that is item 13), so a default
2D build is still unchanged and never touches the network.

### Resolved decisions applied

1. **DEM delivery = AWS S3 COGs** on the USGS `prd-tnm` staged-products bucket
   (same host as the hydrography archives). The seamless 1"/13" products are
   staged one COG per 1°×1° cell named by its NW corner (`n45w124`), so
   discovery is deterministic and offline-constructible from a lon/lat bbox —
   no discovery API call, mirroring `datasets.py`'s region→URL mapping.
2. **Normalize to NAVD88.** 3DEP 1"/13" are natively NAD83 (EPSG:4269) /
   NAVD88 / meters, so normalization is identity for these tiers and recorded
   verbatim in each tile's provenance. A real transform for non-NAVD88 sources
   is deferred to the raster-normalization stage (item 13).

### What landed

- **`src/dem.py`** (new)
  - `DemProduct` + `TIER_PRODUCTS` registry: `preview`→`1` (1", 30 m),
    `state`→`13` (1/3", 10 m). `local` (1 m) intentionally absent.
  - `cell_name` / `geographic_cells`: deterministic 1-degree grid math from a
    lon/lat bbox (west-edge `floor`, north-edge `floor(lat)+1`), sorted output.
  - `ThreeDEPDiscoverer` (a `TileDiscoverer`): one `TileRef` per covering cell;
    accepts a shapely-like `.bounds` object or a 4-tuple; raises
    `ElevationError` for unsupported tiers (`local`) with a clear message.
  - `dem_descriptor`: bridges a `TileRef` to a `FileDescriptor`
    (`dem/<product_key>/<file>`) so the existing `Cache` + `DownloaderLike`
    provide resume/verify/record for free.
  - `acquire_dem`: discovers, downloads-or-reuses (reuse vs `refresh` policy),
    computes each tile's `sha256:` checksum, and builds a per-tile
    `ElevationProvenance` (source product/URL, injected retrieval date,
    EPSG:4269 / NAVD88 / meters, cell size, `{tier, delivery}` lineage).
    Returns `DemAsset(tile, path, provenance)` in deterministic order.

### Tests

- `tests/test_dem.py` (9): grid naming, `preview`/`state` URL + resolution,
  unsupported-tier rejection, registry contents, download+cache+provenance,
  cache-hit reuse (no re-download), `refresh` re-download, and determinism
  (same inputs → same tile URLs + checksums with a fixed clock).

### Verification

- New tests: **9 passed**. Full suite: **217 passed** (was 208; +9), no
  regressions. Smoke: Oregon bbox → 45 deterministic 1" tiles with correct
  `prd-tnm` COG URLs; `local` raises `ElevationError`.
- `ruff` not installed in the offline venv; not run.

### Deferred

The 1 m `local` tier (project/UTM-tiled, needs project-based discovery) and all
raster I/O (mosaic/clip/reproject/sample) — the latter is item 13 (Group 3).
