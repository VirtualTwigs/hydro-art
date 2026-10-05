# Operations Guide

Day-to-day procedures for operating the hydro-art pipeline, managing data, fulfilling orders, and maintaining the system.

## Storage architecture

Three storage roots, all redirectable:

| Root | Default | Purpose |
|------|---------|---------|
| `cache/` | `/Volumes/home/data/incoming` (NAS) or local `cache/` | Downloaded GDB zip archives |
| `datasets/` | `datasets/` | Extracted GDB directories (one per HUC4) |
| `output/` | `output/` | Rendered SVG/PNG/PDF output |

Override via CLI flags (`--cache-dir`, `--datasets-dir`, `--output-dir`), `--external-root`, or `$HYDRO_ART_EXTERNAL_ROOT`.

When `--external-root` is set and the drive is mounted, all three roots expand to `<root>/cache`, `<root>/datasets`, `<root>/output`. When unset, the cache falls back to the NAS share when mounted, else local `cache/`.

**NAS path:** `smb://192.168.0.76/home` mounts at `/Volumes/home`. The hydro-art external root is `/Volumes/home/data/hydro-art`.

## Running a production render

### Single state (2D SVG)

```bash
python build.py --region Washington --palette neon --glow --output svg pdf png
```

The pipeline runs 12 stages in order:
`download -> extract -> validate -> repair_geometries -> reproject -> clip_to_region -> build_graph -> compute_watersheds -> assign_colors -> generate_svg -> optimize_svg -> export`

Downloads are skipped when datasets are already extracted (`datasets/<id>/<huc4>/` exists and is non-empty).

### County-scoped render

```bash
python build.py --region Washington --county "Clark County" --output svg
```

### Art-quality renders (tools/)

The `tools/` scripts produce art-quality output with flow-scaled widths, HUC-N coloring, glow, and layered rasterization:

```bash
python tools/render_state_svg.py --state Washington         # SVG only
python tools/render_state_mono.py --state Washington         # monochrome/elevation
python tools/render_state_3d.py --state Washington           # 3D terrain
python tools/render_state_yoy.py --state Washington --start 2020 --end 2024  # year-over-year
python tools/render_state_monthly.py --state Washington --year 2023          # monthly flow
python tools/render_state_allfeatures.py --state Washington  # all feature layers
```

### CONUS composite

```bash
python tools/composite_usa.py
```

### Deterministic output

For byte-identical output, pin timestamps:

```bash
SOURCE_DATE_EPOCH=0 python build.py --region Oregon --output svg pdf
```

Verify determinism:
```bash
python tools/verify_determinism.py --region Oregon
```

## Database operations

### JSON store (default)

Orders are stored as JSON files under `output/orders/` by default. No setup required.

### PostgreSQL ledger (optional)

Set `DATABASE_URL` to enable:

```bash
export DATABASE_URL="postgresql://user:pass@host:5432/hydro_art"
```

Apply migrations:
```bash
python tools/migrate_ledger.py
```

Migrations are in `migrations/` (001 through 003). The migrator tracks applied migrations in a `_migrations` table.

Import legacy JSON data:
```bash
python tools/import_legacy.py --dry-run    # preview
python tools/import_legacy.py              # apply
```

The server auto-detects: if `DATABASE_URL` is set and connectable, it uses PostgreSQL; otherwise it falls back to JSON silently.

## Order fulfillment

```bash
python tools/fulfill_order.py --order-id <id>
```

The fulfillment pipeline enforces a rights gate (`fulfillment.assert_sellable`):
- USGS NHDPlus/NHD/WBD/3DEP: public domain, sellable with attribution
- nClimGrid-Monthly: public domain, sellable with attribution
- **PRISM: NOT public domain -- never ship commercially** (A/B testing only)

## Gallery and catalog management

```bash
# Scan output/ and ingest new renders
python tools/catalog.py ingest

# Review lifecycle
python tools/catalog.py list
python tools/catalog.py review <entry-id>
python tools/catalog.py publish <entry-id>
python tools/catalog.py archive <entry-id>

# Export public gallery to web
python tools/catalog.py export-public    # writes web/data/gallery.json
```

Status lifecycle: `draft -> review -> published -> archived`.

## Email delivery

Requires a Gmail app password:

```bash
export HYDRO_ART_GMAIL_APP_PASSWORD="your-app-password"
python serve.py
```

The server shows `[green]configured` or `[yellow]not configured` at startup.

## Data acquisition

### Bulk download NHDPlus HR data

```bash
python tools/bulk_download.py --state Washington
```

### Acquire DEM tiles (3DEP)

```bash
python tools/acquire_dem.py --state Washington
```

### Fetch climate data

```bash
python tools/nclimgrid_fetch.py --state Washington --start 2020 --end 2024
python tools/nclimgrid_flow.py --state Washington --year 2023
```

### Add a new state

Derive the HUC4 mapping and wire it into the allowlists:

```bash
python tools/derive_state_huc4.py --state Utah
```

Then add the state to `SUPPORTED_REGIONS` in `src/config.py`.

## Docker demo

The static demo container serves the web pages with pre-rendered SVGs (no GDAL, no live rendering).

```bash
# Stage the display SVGs from NAS
bash deploy/stage-artifacts.sh

# Build and start
docker compose -f deploy/docker-compose.yml up --build -d

# Access at http://localhost:8080/

# Stop
docker compose -f deploy/docker-compose.yml down

# Rebuild after web changes
docker compose -f deploy/docker-compose.yml up --build -d
```

The container runs Python's stdlib `http.server` on port 8080. Pre-rendered SVGs are bind-mounted read-only from `deploy/output/`.

## Health checks and monitoring

### Detect unfinished work

```bash
python tools/detect_unfinished.py
```

Reports: open spec tasks, missing retrospectives, uncommitted changes, stale HANDOFF bullets.

### Release readiness

```bash
python tools/release_gate.py                  # full gate (needs GDAL + data)
python tools/release_gate.py --offline-only   # fixture-match only
```

### Coverage

```bash
python tools/coverage_report.py --fail-under 90
```

### Changelog

```bash
python tools/build_changelog.py          # generate
python tools/build_changelog.py --check  # verify up to date
```

## Updating status documents

```bash
python tools/update_status.py    # stamps HANDOFF.md + roadmap on epoch close
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Permission denied: '/Volumes/home'` | NAS not mounted. The pipeline falls back to local `cache/`; or mount via Finder (smb://192.168.0.76/home). |
| `ruff: command not found` | `.venv/bin/pip install ruff` |
| `ModuleNotFoundError: geopandas` | Install the full GIS stack: `.venv/bin/pip install -r requirements.txt` |
| `ConfigError` (exit 1) | Invalid config value. Check `config.yaml` and CLI flags against allowlists in `src/config.py`. |
| `AcquisitionError` (exit 2) | Data download/extraction failed. Check network, NAS mount, disk space. |
| PDF/PNG timestamps differ | Set `SOURCE_DATE_EPOCH=0` before running. |
| `DATABASE_URL` set but JSON fallback | PostgreSQL unreachable. Check connection string, server status. The server logs the fallback. |
