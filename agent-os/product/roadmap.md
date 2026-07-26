# Product Roadmap

1. [ ] Configuration & CLI foundation — Load a YAML config and parse CLI flags (`--region`, `--palette`, `--glow`, `--output`) into a validated, typed settings object that drives every downstream stage, with `python build.py` runnable end-to-end as a no-op pipeline. `S`

2. [ ] Dataset acquisition & cache — Discover and download the required USGS NHDPlus HR / NHD / WBD files for the selected region, with resumable downloads, integrity verification, archive extraction, metadata storage, and a persistent cache that avoids duplicate downloads. `L`

3. [ ] Data loading & geometry validation/repair — Load downloaded hydrography layers via GeoPandas/pyogrio and automatically repair invalid polygons, self-intersections, empty/collapsed geometries, duplicate vertices, and multipart inconsistencies, emitting repair statistics. `M`

4. [ ] Projection & region clipping — Normalize all layers to internal EPSG:5070, support optional EPSG:4326/3857, and clip the hydrography to the configured region boundary, preserving all river classes with no simplification unless requested. `M`

5. [ ] Hydrography graph construction — Build a directed river network graph (nodes = junctions, edges = segments) supporting upstream/downstream traversal, basin extraction, and network statistics. `M`

6. [ ] Stream ordering & watershed grouping — Compute selectable stream hierarchy (Strahler/Shreve/Hack/custom) and group segments into selectable HUC levels (HUC2–HUC12) for downstream coloring and SVG layering. `M`

7. [ ] Deterministic basin coloring — Assign colors so adjacent watersheds maximize contrast via graph coloring followed by neon-palette assignment, guaranteeing identical colors from identical inputs (no randomness). `S`

8. [ ] Layered SVG rendering — Render every river as a round-capped, round-joined vector path grouped by watershed into a layered SVG on a black background, with default styling and optional stream-order/drainage/discharge width scaling. `L`

9. [ ] Optional glow & SVG optimization — Add pure-vector or Gaussian-blur glow modes with configurable radius, then run SVGO to optimize duplicate paths, unused defs, style repetition, coordinate precision, and grouping. `M`

10. [ ] Multi-format export & reproducibility hardening — Export optional PDF/PNG (with tiled rendering up to 65536px)/TIFF/EPS from the SVG and verify the full single-command workflow produces byte-identical results from identical inputs. `L`

> Notes
> - Order follows the GIS pipeline data dependencies: config → download → clean → project → graph → order → color → render → optimize → export.
> - Each item is an end-to-end, independently testable stage that plugs into the `build.py` pipeline.
> - Effort scale: XS=1 day, S=2-3 days, M=1 week, L=2 weeks, XL=3+ weeks.
