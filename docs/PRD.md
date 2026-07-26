# Hydrographic Vector Art Generator

## Product Requirements Document (PRD)

**Version:** 1.0
**Status:** Initial Development
**Audience:** Claude Opus (Primary Implementer)
**Primary Language:** Python 3.12+

---

# 1. Objective

Develop a fully automated, production-grade GIS and vector graphics pipeline capable of generating museum-quality hydrographic artwork inspired by topographic watershed visualizations.

**Important**

The software SHALL NOT trace or copy any existing artwork. Instead, it SHALL construct entirely original artwork directly from public hydrographic datasets. The output should resemble the visual aesthetic of colorful hydrographic river maps while remaining an original work derived exclusively from public geographic data.

---

# 2. Primary Deliverable

Generate an infinitely scalable SVG representing:
- Oregon
- Washington

with:
- every available river
- every stream
- tributaries
- intermittent waterways
- drainage channels

rendered as colorful vector paths on a black background.

The SVG must remain editable in Illustrator, Affinity Designer, Figma, and Inkscape.

---

# 3. High-Level Goals

The project must:
- Automatically download datasets
- Cache datasets
- Process GIS data
- Generate watershed graph
- Assign basin colors
- Produce SVG
- Produce optional PDF
- Produce optional PNG
- Be reproducible
- Require no manual GIS editing

---

# 4. Design Philosophy

The generated artwork should exhibit:
- extreme geometric fidelity
- high information density
- mathematical precision
- strong visual contrast
- neon-inspired color palette
- clean vector paths
- publication-quality output

The project should prioritize geographic correctness over artistic shortcuts.

---

# 5. Functional Requirements

## 5.1 Geographic Scope

Initial release:
- Oregon
- Washington

Future support:
- California
- Idaho
- Montana
- British Columbia
- Entire United States
- Worldwide

Region selection must be configurable.

## 5.2 Supported Datasets

Priority order:
- **USGS NHDPlus HR** — Primary source.
- **USGS National Hydrography Dataset** — Fallback.
- **Watershed Boundary Dataset** — Used for HUC polygons.
- **HydroSHEDS** — Optional.
- **MERIT Hydro** — Optional.

---

# 6. Automatic Dataset Download

The software shall: discover required files, download, resume downloads, verify integrity, extract archives, maintain local cache, avoid duplicate downloads, store metadata, detect newer releases.

---

# 7. Data Storage

```
datasets/
cache/
output/
logs/
```

Cache should persist between runs.

---

# 8. GIS Pipeline

```
Download
↓ Extract
↓ Validate
↓ Repair geometries
↓ Normalize projections
↓ Clip to region
↓ Build hydrography graph
↓ Compute watersheds
↓ Assign colors
↓ Generate SVG
↓ Optimize SVG
↓ Export
```

---

# 9. Coordinate Systems

- Internal: EPSG:5070
- Optional: EPSG:4326, EPSG:3857

SVG coordinates should be projected into a cartesian coordinate system.

---

# 10. Geometry Validation

Automatically repair: invalid polygons, self intersections, empty geometries, duplicate vertices, collapsed geometries, multipart inconsistencies.

---

# 11. River Preservation

The system shall preserve: major rivers, medium rivers, small rivers, tiny tributaries, intermittent streams, seasonal streams, braided channels, distributaries, optional canals.

No simplification unless requested.

---

# 12. Stream Hierarchy

Support: Strahler, Shreve, Hack, Custom weighting. User selectable.

---

# 13. Watersheds

Support: HUC2, HUC4, HUC6, HUC8, HUC10, HUC12. Selectable.

---

# 14. Graph Construction

Construct a directed graph. Each node: river junction. Each edge: river segment.

Support: upstream traversal, downstream traversal, basin extraction, stream ordering, network statistics.

---

# 15. Basin Coloring

Do NOT assign random colors. Instead: generate deterministic colors. Adjacent watersheds should maximize color contrast. Preferred algorithm: graph coloring followed by palette assignment.

---

# 16. Palette

Inspired by neon cartography. Include: cyan, electric blue, indigo, purple, violet, magenta, orange, gold, lime, teal, turquoise, green. No muted colors. Black background.

---

# 17. Rendering

Every river must be: vector path, round caps, round joins, uniform width by default.

Optional width scaling: stream order, drainage area, discharge.

---

# 18. SVG Architecture

```
<svg>
  <defs/>
  <g id="background"/>
  <g id="watershed_001"/>
  <g id="watershed_002"/>
  ...
</svg>
```

Group rivers by watershed.

---

# 19. Styling

Default: Background #000000, stroke width 0.35px, line cap round, join round, opacity 100%. No fills.

---

# 20. Optional Glow

- Mode A: Pure vector
- Mode B: SVG Gaussian blur

Configurable radius.

---

# 21. SVG Optimization

Run SVGO automatically. Optimize: duplicate paths, unused defs, style repetition, coordinate precision, grouping.

---

# 22. Output Formats

- Required: SVG
- Optional: PDF, PNG, TIFF, EPS

---

# 23. PNG Export

Support: 4096 px, 8192 px, 16384 px, 32768 px, 65536 px. Tile rendering for extremely large images.

---

# 24. CLI

```
python build.py
python build.py --region washington
python build.py --palette neon
python build.py --glow
python build.py --output svg pdf png
```

---

# 25. Configuration

YAML example:

```yaml
region:
  - Oregon
  - Washington
projection: EPSG:5070
stream_order: all
background: "#000000"
line_width: 0.35
palette: neon
glow: false
output:
  svg: true
  png: true
  pdf: true
```

---

# 26. Performance

Support datasets containing millions of river segments. Use: multiprocessing, streaming, chunk processing, vectorized geometry operations. Avoid unnecessary memory duplication.

---

# 27. Logging

Rich terminal output. Include: progress bars, timing, warnings, download progress, geometry repair statistics, export statistics.

---

# 28. Error Recovery

Gracefully recover from: network failures, invalid shapefiles, projection errors, missing attributes, partial downloads, corrupted archives.

---

# 29. Dependencies

Python, GeoPandas, Pyogrio, GDAL, Shapely, Fiona, NumPy, SciPy, NetworkX, PyYAML, svgwrite, lxml, rich, tqdm, matplotlib, SVGO, pytest.

---

# 30. Code Quality

Entire project must include: PEP8, type hints, docstrings, unit tests, integration tests, modular architecture, dependency injection, no global state.

---

# 31. Project Structure

```
hydro-art/
  README.md
  pyproject.toml
  requirements.txt
  config.yaml
  build.py
  download.py
  datasets.py
  projection.py
  graph.py
  watersheds.py
  palette.py
  renderer.py
  svg_writer.py
  optimizer.py
  utils.py
  tests/
  cache/
  datasets/
  output/
  logs/
```

---

# 32. Future Features

Support: interactive SVG, zoomable web viewer, animated river drawing, custom palettes, terrain shading, bathymetry, 3D extrusion, vector tiles, GeoJSON export.

---

# 33. Acceptance Criteria

The project is complete when it can:
- Download all required public datasets automatically.
- Build a complete Oregon + Washington hydrographic network.
- Preserve the maximum practical river detail.
- Generate deterministic watershed colors.
- Export a clean, layered SVG.
- Produce artwork suitable for wall-sized printing.
- Reproduce identical results from identical inputs.
- Complete the workflow with a single command.

---

# 34. Implementation Guidance

Implement this project as a professional open-source GIS application rather than a proof of concept. Prioritize: correctness, geographic accuracy, clean architecture, performance, maintainability, extensibility, deterministic outputs, comprehensive documentation.

When architectural decisions arise, favor modularity and testability over brevity. The resulting codebase should be suitable for long-term maintenance and capable of being extended to additional geographic regions and datasets with minimal changes.
