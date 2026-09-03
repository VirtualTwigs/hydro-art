## Tech stack

Hydrographic Vector Art Generator — a deterministic GIS→SVG CLI. There is no web
framework, database, ORM, or hosted service. Ignore standards that assume those.

### Framework & Runtime
- **Application type:** command-line tool / library (`build.py`, `src/`), no web framework
- **Language/Runtime:** Python 3.12+ (running 3.14.x)
- **Package Manager:** pip; core deps in `pyproject.toml` (`pyyaml`, `rich`),
  heavy GIS stack in `requirements.txt` (lazy-imported behind seams)

### GIS / numeric stack (lazy-imported behind injected seams, never at `src/` top level)
- **Vector:** shapely, geopandas, pyogrio, networkx
- **Raster (optional):** rasterio, numpy
- **Internal CRS:** EPSG:5070 (single source: `src/crs.py:INTERNAL_CRS`)
- **Data sources:** USGS NHDPlus HR / NHD / WBD (public domain); 3DEP DEM COGs on
  AWS S3; NOAA NCEI nClimGrid-Monthly climate (public domain)

### Frontend (`web/`, no build step)
- **JavaScript:** vanilla ES, classic `<script src>`, `file://`-safe
- **CSS:** custom (`web/shared/ux.css`); no framework
- **Shared logic:** `web/shared/hydro-ux.js` — must stay Node-loadable

### Testing & Quality
- **Test Framework:** pytest (offline suite — no GDAL/network/data) + a CommonJS
  `node` roundtrip test (`tests/test_recipe_roundtrip.cjs`)
- **Linting/Formatting:** ruff (line-length 88)
- **Determinism:** golden-hash registry + `tools/verify_determinism.py`

### Storage & Infrastructure
- **Large data:** Synology NAS (`/Volumes/home/data/hydro-art/…`), redirectable
  via `src/storage.py` (`--external-root` / `$HYDRO_ART_EXTERNAL_ROOT`)
- **External CLI tools (optional, degrade gracefully):** `svgo`, `rsvg-convert`

### Third-Party Services
- None (no auth, email, or monitoring). Fully local/offline pipeline.
