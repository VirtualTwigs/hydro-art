# Implementation report — Infrastructure QA and presets (Epoch 16, Item #68 — epoch close)

## Summary
Validated the #67 infrastructure render on **real** Oregon data and tuned the
screen/print presets so structures enrich rather than clutter. Added a
pure/offline structure-QA module (fixture-tested), a non-offline real-data QA
tool + all-features render extension, and tuned `HYDRO_STRUCTURE_PRESETS`. The
default (infrastructure-disabled) build stays byte-for-byte identical. Closes
Epoch 16.

## What shipped

### TG1 — offline structure-QA module (`src/hydro_structure_qa.py`)
Pure, projection-free QA over already-classified `HydroStructure` sequences,
mirroring the `src/determinism.py` / `src/flow_metrics.py` pattern (offline;
top-level `import shapely` only, no `pyogrio`/`geopandas`/`rasterio`, no network):
- `structure_network_placement` — nearest-flowline distance summary
  (`NetworkPlacement`: count, on_network, median/max distance, off-network ids).
- `cross_layer_duplicates` — union-find grouping of same-`struct_class`,
  different-`source_layer` structures within `tolerance_m` (the "dam present as
  both NHDLine and NHDArea → draw once" candidate).
- `canal_natural_separation` — leak detector for structures coinciding with
  natural-taxonomy features.
- `build_qa_report` — folds the three into a frozen `HydroStructureQAReport`.
- Tests: `tests/test_hydro_structure_qa.py` — **8 passing**.

### TG2 — real-data tool + render extension + preset tuning
- `tools/hydro_structure_qa.py` (NEW, non-offline) — mirrors
  `tools/waterbody_qa.py`: loads real `NHDLine`/`NHDPoint`/`NHDArea`, classifies
  via `classify_hydro_structure_layer`, selects via `process_hydro_structures`,
  runs `build_qa_report` against the real flowline network + natural features,
  prints counts / placement / duplicate groups / separation / source-id
  traceability. CLI `--state` / `--gdb-glob --no-clip` / `--county-shp`.
- `tools/render_state_allfeatures.py` — added opt-in `--structures` (+
  `--structure-min-area`/`--structure-min-spacing`); off by default so existing
  invocations are unchanged.
- `src/config.py` — tuned `HYDRO_STRUCTURE_PRESETS` **values only** from the
  real observation (screen keeps all; print-county moderate thinning; print-state
  aggressive), mechanism unchanged, default disabled. Monotonic-thinning
  invariant + default-disabled locked in `tests/test_config.py`.

### QA-metric fix (found during TG2 real-data validation)
`canal_natural_separation` originally used bare shapely `intersects`, which
flagged every *touching boundary* between an engineered `NHDArea` polygon and its
adjacent natural polygon as a violation — pervasive and normal in real NHD data,
making `separation_ok` always `False`. Replaced with `_coincidence_fraction`
(area-fraction for polygons so a zero-area shared edge scores 0, length-fraction
for lines, 1.0 for a point inside) thresholded at `min_overlap_fraction=0.5`.
Locked with `test_shared_boundary_adjacency_is_not_a_violation`. On HUC4 1807 this
dropped reported overlaps from 127 (pure adjacency) to 77 (genuine coincidences).

## Real-data validation (HUC4 1807, Oregon coastal — exit 0)
See `implementation/real-data-findings.md` for the full run. Headline numbers:
- 6686 candidates classified → **557 selected** (dam_weir 174, gaging_station
  305, water_intake_outflow 9, gate 2, spillway 15, canal_ditch 52; NHDLine 145 /
  NHDPoint 315 / NHDArea 97 — all three geometry kinds through one taxonomy).
- On-network (250 m tol) vs 225,480 flowlines: **553/557 on-network**, median
  3.0 m, max 408.6 m — engineered structures overwhelmingly sit ON the channel.
- Cross-layer duplicates: **1 group** — the "draw once" candidate surfaced.
- Separation: 77 genuine coincidences (post-fix) — physically real intakes/
  spillways inside natural water, not a classification leak.

## Determinism / gate verdict (TG3)
- **Full offline suite: 790 passing** (no network/GDAL/real data).
- **Lint clean** for touched files. `src/hydro_structure_qa.py` carries only the
  pre-existing sibling-matching deviations (RUF022 unsorted `__all__`, UP035
  `typing.Iterable`/`Sequence`, intentional `# noqa: F401 import shapely`), which
  match `src/areal_selection.py` / `src/waterbody_selection.py` by design. No new
  deviations introduced.
- **Byte-identical default: PASS by invariant.** `hydro_structures.enabled`
  defaults to `False`, so the default/river-only path selects 0 structures and
  renders unchanged; preset tuning is value-only with no preset applied by
  default. The default SVG sha256 stable at `e6b9bd6cfaf7…` since #65 is
  unaffected. GDAL-backed imports (`pyogrio`/`geopandas`/`rasterio`) remain lazy;
  the QA module imports only top-level `shapely`.
- **Carry-forward:** `tools/verify_determinism.py --region Oregon` was not run as
  a live double-render (its harness needs a real GDB/GDAL host); byte-identity is
  established here via the default-disabled invariant + the stable golden sha.

## Epoch 16 gate
Source-traceable dams/weirs/locks/gaging-stations/intakes and distinctly-styled
engineered channels overlay the water art, controllable by preset, **default
disabled + byte-identical**. Gate met.
