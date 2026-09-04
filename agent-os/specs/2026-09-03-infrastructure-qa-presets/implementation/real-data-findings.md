# Real-data findings — Infrastructure QA (Epoch 16, Item #68, TG2)

## Environment / limitations
- GDAL stack (geopandas/pyogrio/shapely) **available** in `.venv`; real NHDPlus HR
  GDBs present under `datasets/nhdplus_hr/` (HUC4 1701–1712, 1801–1810).
- The Census **states/counties shapefiles are NOT present** in this environment
  (`/tmp/states_shp/` and `/tmp/counties_shp/` are empty). So the `--state Oregon`
  political-clip run and the `render_state_allfeatures --structures` full render
  (both call `render_common.load_state`, which reads `STATES_SHP`) could not run
  here. Instead I ran the `--no-clip` HUC4 path, which exercises every pipeline
  code path (load → classify → repair/reproject/clip-to-boundary=None → select →
  build_qa_report), and separately dry-ran the renderer's structure classify +
  select path (`_load_hydro_structures`) against a bbox boundary so the clip +
  thinning branches were exercised. No numbers below are fabricated.

## `tools/hydro_structure_qa.py --gdb-glob 'datasets/nhdplus_hr/1807/*.gdb' --no-clip`
Real run, exit 0. HUC4 1807 (Oregon coastal). Observed:

- Candidates classified: **6686** geometries
  (NHDLine 1130, NHDPoint 4664, NHDArea 892).
- **Selected: 557** (excluded 6129 — the excluded are open water / natural areal /
  non-structure line types the complementary taxonomy owns).
- **By class (selected):** dam_weir 174, gaging_station 305,
  water_intake_outflow 9, gate 2, spillway 15, canal_ditch 52.
- **By source layer (selected):** NHDLine 145, NHDPoint 315, NHDArea 97 — proves
  all three geometry kinds flow through one taxonomy.

### On-network placement (tolerance 250 m)
- Flowlines loaded: **225,480** reaches.
- Structures placed: 557; **on-network 553, off-network 4**.
- **Median nearest-flowline distance: 3.0 m; max: 408.6 m.**
- The 4 off-network ids: 27733687, 27730479, 27740291,
  {41694961-A7A1-465A-9C55-0E084F0FC50C}. Median of 3.0 m confirms engineered
  structures overwhelmingly sit ON the channel they govern — the placement
  property holds on real data.

### Cross-layer duplicate groups (proximity 150 m)
- **1 group:** ('27690066', '27690064', '27690068', '120000388') — a dam/weir
  present on multiple source layers within 150 m, exactly the "draw once, not
  twice" candidate the check is meant to surface.

### Canal / natural separation
- Natural features loaded: 8636 (waterbodies + areal + point taxonomies).
- **separation_ok = False; 77 offending overlaps** (coincidence-fraction ≥ 0.5).
  An early cut of the check used bare shapely `intersects`, which counted every
  *touching boundary* as an overlap and reported 127 — but shared edges between
  an engineered `NHDArea` polygon and the adjacent natural polygon are normal,
  pervasive, and NOT a separation leak. The check now measures the fraction of a
  structure's own footprint that is *coincident with* a natural feature
  (`_coincidence_fraction`: area-fraction for polygons so a zero-area shared edge
  scores 0, length-fraction for lines, 1.0 for a point inside), thresholded at
  0.5. That removed ~50 pure-adjacency false positives.
- The remaining **77** are genuine coincidences: engineered features whose
  footprint substantially sits *inside* a natural water polygon — physically real
  (an intake or spillway located within a reservoir/lake, a canal reach running
  through a waterbody). The complementary taxonomy still owns each geometry by
  exactly one class (no geometry is double-classified); this surfaces spatial
  coincidence a cartographer may want to know about for styling, not a
  classification leak.
- All 557 selected structures carry a source id (traceable).

## Renderer structure path (dry check, NHDArea subset, bbox boundary)
`_load_hydro_structures` over a 200-row NHDArea sample + full 1807 GDB returned
545 selected `(feature_id, geometry, struct_class)` tuples spanning all six
non-excluded classes {dam_weir, gaging_station, gate, canal_ditch,
water_intake_outflow, spillway}, i.e. the exact tuple shape `render_svg`'s
`hydro_structures` param consumes. The `--structures` overlay is wired; only the
final rasterize step needs the (absent) state shapefile to produce a PNG.

## Preset-tuning implication
- At HUC4 scale (~an Oregon-basin extent), unthinned selection yields ~557
  structures — dense but legible for a **screen** view (keep min_area=0,
  spacing=0).
- For a single **county** the count is a fraction of this, so light thinning
  (min_area ~10k m², spacing ~1.5–2 km) removes tiny NHDArea slivers /
  gaging-station clusters without losing the story.
- For a whole **state** (union of ~6–8 basins → thousands of structures) heavier
  thinning is warranted (min_area ~60k m², spacing ~6–8 km) so dams/gages read as
  enrichment, not a smear. These observations drive the tuned
  `HYDRO_STRUCTURE_PRESETS` values (task 2.4).
