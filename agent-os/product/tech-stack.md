# Tech Stack

Technical stack for the Hydrographic Vector Art Generator. Choices are driven by the PRD (`docs/PRD.md`, sections 29–31) and prioritize correctness, geographic accuracy, determinism, and long-term maintainability.

### Framework & Runtime
- **Application Type:** Command-line GIS + vector-graphics pipeline (`build.py` entry point)
- **Language/Runtime:** Python 3.12+
- **Package Manager:** pip (with `pyproject.toml` + `requirements.txt`)

### GIS & Geometry
- **Vector data I/O:** GeoPandas, Pyogrio (fast I/O), Fiona
- **Geometry engine:** Shapely
- **Geospatial backend:** GDAL/OGR
- **Projections:** pyproj (via GeoPandas) — internal EPSG:5070; optional EPSG:4326, EPSG:3857
- **Numerical / scientific:** NumPy, SciPy
- **Graph / network analysis:** NetworkX (directed river graph, traversal, basin extraction, stream ordering)

### Rendering & Output
- **SVG generation:** svgwrite (+ lxml for fine-grained XML control)
- **SVG optimization:** SVGO (Node.js tool, invoked as a subprocess)
- **Raster/other export:** matplotlib and/or cairosvg-class tooling for PNG/PDF/TIFF/EPS (with tiled rendering for very large PNGs)

### Configuration & CLI
- **Config format:** YAML via PyYAML (`config.yaml`)
- **CLI:** argparse (or equivalent) exposing `--region`, `--palette`, `--glow`, `--output`, etc.

### Data Sources
- **Primary:** USGS NHDPlus HR
- **Fallback:** USGS National Hydrography Dataset (NHD)
- **Watershed polygons:** Watershed Boundary Dataset (WBD / HUC)
- **Optional:** HydroSHEDS, MERIT Hydro

### Testing & Quality
- **Test Framework:** pytest (unit + integration)
- **Standards:** PEP8, type hints, docstrings, modular architecture, dependency injection, no global state
- **Linting/Formatting:** ruff / black (recommended; PEP8 enforced)

### Storage & Caching
- **Local layout:** `datasets/`, `cache/`, `output/`, `logs/` (persist between runs; git-ignored)
- **Caching strategy:** File-based persistent cache with stored metadata and integrity verification

### Observability
- **Logging / terminal UX:** rich (progress bars, timing, warnings), tqdm for download/processing progress

### Performance
- **Concurrency:** multiprocessing
- **Data handling:** streaming, chunk processing, vectorized geometry operations; avoid unnecessary memory duplication

### Deployment & Infrastructure
- **Distribution:** Open-source Python package / repository; runs locally via single command
- **CI/CD:** GitHub Actions recommended (run pytest + linting) — not yet configured

### Notes
- **No database:** the pipeline is file-based; hydrography is loaded from downloaded datasets into in-memory GeoDataFrames/graphs.
- **No frontend framework:** output is static SVG (and optional raster/vector exports); a future zoomable web viewer is out of scope for the initial release (see PRD §32).
