# Retrospective — Epoch 16: Hydro-infrastructure layers (#65, #67, #68)

_Closed 2026-09-04. **No pre-registered watch-list** — unlike Epochs 8/9/12/14, none
of the three Epoch 16 spec folders (`2026-09-03-hydro-structure-taxonomy`,
`2026-09-03-infrastructure-rendering`, `2026-09-03-infrastructure-qa-presets`) carries
a `planning/pre-analysis.md`. This is a narrative closeout rather than a graded one; the
missing pre-analysis is itself a process observation (see below)._

## What the epoch was

Add the **engineered water infrastructure NHD already encodes** — dams/weirs, gates,
lock chambers, spillways, gaging stations, water intakes/outflows, and canals/ditches —
across `NHDLine` / `NHDPoint` / `NHDArea`. Still strictly **water-related** and still
**USGS public domain** (sellable, no new Rights gate). The whole epoch rode the
point/line/area rendering seams built in Epoch 15, so it was mostly taxonomy + symbology
+ selection + QA rather than new machinery. This is the layer that turns the art from a
map of *where the water is* into a story about *how people use the water* — dams,
diversions, and gauges on the network they govern.

Three of the four planned items shipped (#65, #67, #68); **#66 was deferred** (see
carry-forward). The epoch closed on #68.

## What shipped

### #65 — Structure source layers & taxonomy (`f06e612`)

`src/hydro_structures.py` — one versioned `HYDRO_STRUCTURE_POLICY_VERSION` FType/FCode
policy table serving **all three** source layers, mirroring `src/point_features.py`
(name-only-refining, missing FType → `excluded` + `missing_ftype`, full provenance, no
geometry math, no top-level GDAL). Classes:
`dam_weir`/`gate`/`lock_chamber`/`gaging_station`/`water_intake_outflow`/`spillway`/
`canal_ditch`/`excluded`. `436 Reservoir` deliberately **stays with waterbodies** (a
documented policy note) so the taxonomy is complementary/disjoint — every geometry is
owned by exactly one taxonomy. `src/loading.py` gained the NHDLine seam
(`LINE_LAYER_ALLOWLIST`, `LINE_ATTRIBUTE_FIELDS`, `discover_line_layers`,
`load_line_features`); NHDPoint/NHDArea already loaded via the Epoch 15/1.5 seams. Codes
domain-verified against real GDB 1807 (343/336/455/485/367 confirmed; 369 line/area +
398 lock_chamber flagged UNCONFIRMED as standard NHD codes). Complementarity tested
(structure codes disjoint from waterbody/point/areal included codes). Taxonomy + loader
only — no rendering, no pipeline wiring, byte-identical. **761 offline tests green.**

### #67 — Infrastructure selection & rendering (`a7cb98f`)

Makes #65's classified structures visible, **disabled by default**. New
`src/hydro_structure_selection.py` (`process_hydro_structures`:
repair→reproject→clip→geometry-type select — polygon `min_area_m2`, point `min_spacing_m`
thinning, line clip-only), mirroring `src/areal_selection.py`. `src/config.py` gained
frozen `HydroStructureSettings` (disabled default) + `HYDRO_STRUCTURE_PRESETS`
(`screen`/`print-state`/`print-county`, expanded at config time like `WaterbodySettings`
so no-preset builds stay byte-identical). `src/rendering.py` gained
`HYDRO_STRUCTURE_GLYPHS` / `DEFAULT_HYDRO_STRUCTURE_STYLES` / `_hydro_structure_lines`
(point glyph / line bar / areal path) + keyword-only
`hydro_structures` / `hydro_structure_order="above"` on `render_svg` (None → no markup, so
dams read on the channel they cross). `src/pipeline.py` adds the **additive** NHDLine
load (`line_layers`), widens the shared NHDPoint/NHDArea load gates, and wires
`_select_hydro_structures`. **780 offline tests green** (+19), default build
byte-identical via live `verify_determinism --region Oregon` (svg sha `e6b9bd6cfaf7…`,
0 structures on the default path).

### #68 — QA & tuned presets (`07c2a63`)

Pure/offline `src/hydro_structure_qa.py` (top-level `import shapely` only, no
`pyogrio`/`geopandas`/`rasterio`, no network), mirroring the
`src/determinism.py`/`src/flow_metrics.py` pattern:
- `structure_network_placement` — nearest-flowline distance summary
  (`NetworkPlacement`: count, on_network, median/max distance, off-network ids).
- `cross_layer_duplicates` — union-find grouping of same-`struct_class`,
  different-`source_layer` structures within `tolerance_m` (the "dam present on both
  NHDLine and NHDArea → draw once" candidate).
- `canal_natural_separation` — coincidence leak detector (see gotcha below).
- `build_qa_report` — folds the three into a frozen `HydroStructureQAReport`.

Plus `tools/hydro_structure_qa.py` (non-offline real-data cross-check, mirrors
`tools/waterbody_qa.py`), an opt-in `--structures` overlay on
`tools/render_state_allfeatures.py`, and **value-only** tuning of
`HYDRO_STRUCTURE_PRESETS` from the real observation (screen keeps all; print-county
moderate thinning; print-state aggressive), with a monotonic-thinning invariant +
default-disabled lock in `tests/test_config.py`. **790 offline tests green** (+10).
`tests/test_hydro_structure_qa.py` — 8 passing. **Closes Epoch 16.**

## Real-data findings (HUC4 1807, Oregon coastal — `tools/hydro_structure_qa.py --no-clip`, exit 0)

This is the evidence offline fixtures could not produce: what real NHDPlus HR encodes at
basin scale.

- **6686 geometries classified → 557 selected** (excluded 6129 — open water / natural
  areal / non-structure line types the complementary taxonomy owns). By class:
  `gaging_station` 305, `dam_weir` 174, `canal_ditch` 52, `spillway` 15,
  `water_intake_outflow` 9, `gate` 2. By source layer: **NHDLine 145 / NHDPoint 315 /
  NHDArea 97** — proving all three geometry kinds flow through the one #65 taxonomy.
- **On-network placement (250 m tolerance) over 225,480 flowline reaches: 553/557
  on-network, median nearest-flowline distance 3.0 m, max 408.6 m.** The 3.0 m median
  confirms engineered structures overwhelmingly sit ON the channel they govern — the
  placement property holds on real data, not just in fixtures. The 4 off-network ids
  (27733687, 27730479, 27740291, {41694961-…}) are recorded, not hidden.
- **1 cross-layer duplicate group** (`27690066`/`27690064`/`27690068`/`120000388`) — a
  dam present on multiple source layers within 150 m, exactly the "draw once, not twice"
  candidate the check exists to surface.
- **Separation: 77 genuine coincidences** (coincidence-fraction ≥ 0.5) against 8636
  natural features — see the gotcha below for why this is 77 and not 127. All 557
  selected structures carry a source id (traceable).

## The bug the real run surfaced (offline fakes could not)

`canal_natural_separation` originally used bare shapely `intersects`. On real NHD data
that flags **every touching boundary** between an engineered `NHDArea` polygon and its
adjacent natural polygon as a violation — shared edges are pervasive and normal, so
`separation_ok` was always `False` and the metric was useless. Fixture geometry (clean,
non-adjacent hand-built shapes) never exhibited this; only the real 1807 GDB, where
engineered and natural polygons abut constantly, exposed it. The fix
(`_coincidence_fraction`: area-fraction for polygons so a zero-area shared edge scores 0,
length-fraction for lines, 1.0 for a point inside, thresholded at
`min_overlap_fraction=0.5`) measures how much of a structure's *own footprint* sits
inside a natural feature. On HUC4 1807 this dropped reported overlaps from **127 (pure
adjacency) to 77 (genuine coincidences)** — ~50 false positives removed. The remaining
77 are physically real (intakes/spillways inside reservoirs, canal reaches through
waterbodies): spatial coincidence a cartographer may want to know for styling, **not** a
classification leak (the complementary taxonomy still owns each geometry by exactly one
class). Locked with `test_shared_boundary_adjacency_is_not_a_violation`. This is the
epoch's most important piece of evidence — the recurring lesson that a metric which is
green on offline fakes can be meaningless on real topology.

## Invariants held

- **Offline suite:** 790 passing (was 761 at #65, 780 at #67; +29 across the epoch). No
  network / GDAL / real data; no GDAL-backed imports leaked into `src/` or `tests/` (the
  QA module imports only top-level `shapely`, matching its
  `src/areal_selection.py`/`src/waterbody_selection.py` siblings).
- **2D default output byte-identical:** yes. `hydro_structures.enabled` defaults to
  `False`, so the default/river-only path selects 0 structures and renders unchanged;
  preset tuning is value-only with no preset applied by default. Default SVG sha256
  stable at `e6b9bd6cfaf7…` since #65.
- **`PIPELINE_STAGES` untouched:** yes — no stage added or reordered. #67 wired the
  additive NHDLine load and widened the shared NHDPoint/NHDArea gates *within* existing
  stages (all gated on setting AND loader support), which is the sanctioned Epoch 15/1.5
  integration pattern, not a `PIPELINE_STAGES` edit.
- **Rights gate:** N/A in the sense that no new gate was needed — NHDPlus/NHD structures
  are the same USGS federal public domain as the rest of the water art, sellable with
  attribution. `fulfillment.assert_sellable` is unaffected.

## What went well

- **The Epoch 15 seam precedent paid off directly.** No new I/O shape was invented:
  `process_hydro_structures` is a same-shape sibling of `process_areal_features`, the QA
  module follows `determinism`/`flow_metrics`, and the real-data tool mirrors
  `tools/waterbody_qa.py`. The epoch was genuinely "taxonomy + symbology + QA," as
  planned, because the plumbing already existed.
- **One taxonomy across three geometry kinds held on real data.** 145 line / 315 point /
  97 area selections all flowed through the single #65 policy table with disjoint,
  complementary classification — the design bet from #65 was confirmed by the 1807 run.
- **QA surfaced exactly the candidates it was designed to.** The 1 cross-layer duplicate
  group and the on-network median of 3.0 m are the concrete "this works" signals, not a
  vague summary.

## Gotchas found

- **`intersects`-based overlap metrics are meaningless on real NHD adjacency** — engineered
  and natural polygons share edges everywhere. Measure footprint-fraction coincidence,
  not boundary touching. (Detailed above.)
- **Census states/counties shapefiles were absent in the #68 environment**
  (`/tmp/states_shp/`, `/tmp/counties_shp/` empty), so the `--state Oregon` political-clip
  render and the full `render_state_allfeatures --structures` PNG could not be produced.
  QA ran the `--no-clip` HUC4 path (which exercises every pipeline code path: load →
  classify → repair/reproject/clip-to-boundary=None → select → build_qa_report) plus a dry
  renderer check of `_load_hydro_structures` (545 selected tuples spanning all six
  non-excluded classes, the exact shape `render_svg`'s `hydro_structures` param consumes).
  **No numbers were fabricated** — the final rasterize step is what needs the absent
  shapefile.
- **No pre-analysis / watch-list was written for any of the three Epoch 16 specs.** The
  Epoch 8/9/12/14 practice of pre-registering risks *before* implementation was skipped
  here. It would have helped: the `intersects` metric bug is precisely the kind of
  "offline fakes can't verify the real path" risk that a watch-list forces you to smoke
  for. Recommend restoring the pre-analysis step for future epochs.

## Carry-forward

- **#66 (canal/ditch/aqueduct/pipeline NHDFlowline styling) was NOT shipped** — still
  `[ ]` in the roadmap; the epoch closed on #68 with #66 deferred. Important nuance:
  engineered `NHDArea` *canals* **are** covered as the `canal_ditch` structure class, but
  the `NHDFlowline` `CanalDitch`/`Pipeline`/`ArtificialPath`/`Connector`/
  `UndergroundConduit` split — distinguishing engineered *reaches on the natural flowline
  network* so they can be dashed/second-colored or excluded — remains unbuilt. This is
  the epoch's main scope gap. The seam work from #65/#67 (allowlists, config-driven
  styling, byte-identical-when-off discipline) is the right template when it's picked up.
- **Byte-identity for #68 rests on the default-disabled invariant + stable golden sha
  (`e6b9bd6cfaf7…`), NOT a live `verify_determinism.py --region Oregon` double-render** —
  that harness needs a GDAL/GDB host. #65 and #67 *did* run the live verify per their
  roadmap notes; #68 did not. This matches the shared Epoch 9/10/14 carry-forward that a
  full byte-identical `build.py` render compare still needs a GDAL host.
- **Real political-clip render + full `--structures` PNG deferred to a host with the
  Census shapefiles staged.** The HUC4 `--no-clip` path validated every code path, but the
  end-to-end state render (clip + rasterize) has not been produced. Open, not passed.
- **Washington / Clark County structure validation.** The #68 spec framed
  Oregon/Washington/Clark County validation; only Oregon HUC4 1807 was run. WA + county
  cross-checks remain to confirm the tuned print-state/print-county presets on real
  county-scale extents.

## Lessons

- **Restore the pre-analysis/watch-list step.** The one process regression this epoch was
  skipping it, and the `intersects` bug is the textbook case a pre-registered
  "offline-fakes-can't-verify-this" risk would have caught earlier.
- **Reusing a proven seam is what let the epoch be small** — resist inventing new I/O
  shapes when a same-signature sibling exists (`process_areal_features`,
  `tools/waterbody_qa.py`).
- **A green offline metric is not a correct metric.** Validate every QA metric against
  real topology before trusting `*_ok` booleans; fixtures rarely reproduce real
  adjacency/coincidence.
- **When a host can't produce the final artifact, exercise every upstream code path and
  say so** — the `--no-clip` + dry-render approach kept the QA honest without fabricating
  a PNG.
