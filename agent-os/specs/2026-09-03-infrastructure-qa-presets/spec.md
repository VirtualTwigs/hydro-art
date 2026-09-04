# Spec: Infrastructure QA and presets (Epoch 16, Item #68 — epoch close)

## Summary
Validate the #67 infrastructure render on REAL Oregon/Washington/Clark data and tune the
screen/print presets so structures enrich rather than clutter. Adds a pure/offline
structure-QA module (fixture-tested), a real-data QA tool + all-features render extension
(non-offline), and tuned `HYDRO_STRUCTURE_PRESETS`. Default (disabled) build stays
byte-for-byte identical. Mirrors the Epoch 1.5 waterbody-QA close (`tools/waterbody_qa.py`).

## Context & templates to mirror (parallel exactly — do not duplicate)
- `tools/waterbody_qa.py` — the real-region QA-tool precedent: runs the SAME pipeline
  classification+selection code against real GDBs, prints a cross-check report; non-offline;
  `--state` / `--gdb-glob --no-clip` / `--county-shp` flags.
- `src/determinism.py` / `src/flow_metrics.py` — the pure-offline `src/` module pattern that
  the offline suite tests, paired with a heavy `tools/` reader.
- `tools/render_state_allfeatures.py` — political-clip all-family preview renderer (rivers +
  waterbodies + areal + points), already wired to `render_svg`; extend to add structures.
- #67: `src/hydro_structures.py` (`classify_hydro_structure_layer`, `HydroStructure`),
  `src/hydro_structure_selection.py` (`process_hydro_structures`, policy), `src/config.py`
  (`HYDRO_STRUCTURE_PRESETS`, `HydroStructureSettings`), `src/rendering.py` (`render_svg`
  `hydro_structures` param).

## Design

### `src/hydro_structure_qa.py` (NEW, offline)
Pure functions over already-classified `HydroStructure` sequences + flowline geometries:
```
HydroStructureQAReport(frozen):
    on_network: NetworkPlacement          # counts, median/max nearest-flowline dist, off-network ids
    duplicate_groups: tuple[tuple[str, ...], ...]   # cross-layer near-duplicate source_id groups
    separation_ok: bool                   # no structure coincides with a natural-taxonomy feature
    overlaps: tuple[...]                  # any offending structure/natural pairs

structure_network_placement(structures, flowlines, *, tolerance_m) -> NetworkPlacement
cross_layer_duplicates(structures, *, tolerance_m) -> tuple[tuple[str, ...], ...]
canal_natural_separation(structures, natural_features) -> tuple[bool, tuple[...]]
build_qa_report(structures, flowlines, natural_features, *, tolerance_m) -> HydroStructureQAReport
```
Distances in `INTERNAL_CRS` (EPSG:5070) — inputs assumed already projected (the pipeline/tool
reprojects before QA), so this module does pure shapely distance/`intersects` math, no reprojection.
Top-level `import shapely` only (matches the selection modules); no `pyogrio`/`geopandas`/`rasterio`;
no network.

### `src/config.py` (MODIFY — preset tuning only)
Re-tune `HYDRO_STRUCTURE_PRESETS` values (`screen` keeps all; `print-county` moderate thinning;
`print-state` aggressive thinning) plus `size`/`opacity`/`dash` so infrastructure reads at each
scale. Mechanism unchanged (`_coerce_hydro_structures`); **default disabled** so no default-build
change. Lock the monotonic-thinning invariant in `tests/test_config.py`.

### `tools/hydro_structure_qa.py` (NEW, non-offline)
Mirror `waterbody_qa.py`: load real `NHDLine`/`NHDPoint`/`NHDArea` via the pipeline loaders,
classify via `classify_hydro_structure_layer`, select via `process_hydro_structures`, then run
`src.hydro_structure_qa.build_qa_report` against the real flowline network + natural features and
print counts / placement / duplicate groups / separation / source-id traceability. Same CLI shape
(`--state`, `--gdb-glob --no-clip`, `--county-shp/--county/--state-fp`). Eager GIS imports.

### `tools/render_state_allfeatures.py` (MODIFY)
Add an opt-in flag (e.g. `--structures`) that selects + draws hydro structures via the `render_svg`
`hydro_structures` param, above the water layers. Off by default → existing invocations unchanged.

## Acceptance criteria
- `src/hydro_structure_qa.py` exists with a matching `tests/test_hydro_structure_qa.py`; offline
  (no GDAL beyond top-level shapely, no network); the three QA properties are computed correctly on
  hand-built fixtures (on-network vs off-network, a cross-layer duplicate pair, a separation
  violation vs clean).
- `HYDRO_STRUCTURE_PRESETS` tuned; monotonic thinning (`print-state` ≥ `print-county` ≥ `screen`
  in `min_area_m2`/`min_spacing_m`) asserted; default disabled → default build byte-identical.
- `tools/hydro_structure_qa.py` runs the pipeline code against a real OR/WA GDB and prints the QA
  report; `render_state_allfeatures.py` can render structures on a real state (visually confirmed).
- The DEFAULT build is byte-for-byte identical (`tools/verify_determinism.py`); no new top-level
  GDAL import in any default `src/` path.
- Full offline suite passes (no network/GDAL/real data); lint clean.
- **Epoch 16 gate:** a build can overlay source-traceable dams/weirs/locks/gaging-stations/intakes
  and distinctly-styled engineered channels on the water art, controllable by preset, default
  disabled + byte-identical.

## Risks / notes
- Keep QA math pure and projection-free — the caller (pipeline/tool) reprojects to EPSG:5070 first;
  the offline tests build geometries already in a metric frame.
- Real-data tasks (TG2) are non-offline and depend on a mounted/extracted GDB — the offline gate
  (TG3) must not depend on them.
- Preset tuning is value-only; do not alter the coercion/validation mechanism or the default.
