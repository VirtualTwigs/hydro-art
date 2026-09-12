# Internal test deployment (static)

A small, GDAL-free container that serves the `web/` control surface plus the two
pre-rendered display SVGs, so internal folks can click the real UX and view real
river geometry from your laptop. **No live rendering** — the "Run pipeline"
button needs the heavy GIS backend (see *Live renders* below).

## What testers can do

| Page | Works statically? | Notes |
|------|-------------------|-------|
| `start.html` (served at `/`) | yes | Customer-facing landing. Real Clark County / Washington renders — animated seasonal-flow hero + poster/report/digital/animation catalog. Needs the `deploy/output/landing/` WebP assets staged (see below). |
| `studio.html`   | yes | Client-side procedural previews + mapping to the `build.py` command / `config.yaml`. Live render disabled. |
| `gallery.html`  | yes | Real curated rights ledger (region/style/endpoint/sellable metadata). |
| `report.html`   | yes | Watershed report with baked-in real metrics/figures. |
| `3d.html`       | yes | **Real Oregon & Washington river geometry** (84k paths) in a WebGL terrain model. |
| `experience.html` | partial | Loads a delivery JSON via the file picker. |
| `index.html`    | partial | Early-concept page; loads the SVG but its basin animation keys off a group structure this export doesn't use. |

## Build & run

The repo's `output/` and `datasets/` are **symlinks to the NAS**, which the
Docker VM can't bind-mount. So first stage local copies into `deploy/output/`
(a real local dir, git-ignored): the two display SVGs, plus the down-scaled
WebP landing assets under `deploy/output/landing/` that `start.html` shows
(real Clark County / Washington renders — needs `sips`, `cwebp`, `gif2webp`):

```bash
# from the repo root — needs the NAS mounted
bash deploy/stage-artifacts.sh

docker compose -f deploy/docker-compose.yml up --build -d
# (this machine's compose is the standalone binary: `docker-compose -f ... up --build -d`)

# plain docker, no compose (mount the staged dir read-only):
docker build -f deploy/Dockerfile -t hydro-art-demo .
docker run -d --name hydro-art-demo -p 8080:8080 \
  -v "$PWD/deploy/output:/app/output:ro" hydro-art-demo
```

Local check: <http://localhost:8080/> → links to every demo page.

Stop / rebuild:
```bash
docker compose -f deploy/docker-compose.yml down
docker compose -f deploy/docker-compose.yml up --build -d   # after web/ changes
```

The image holds only `web/`; the display SVGs and the `landing/` WebP assets
come from `deploy/output/` mounted read-only at runtime. After re-rendering any
source (e.g. `tools/render_state_svg.py`, `tools/render_county_clip.py`,
`tools/render_monthly.py`), re-run `bash deploy/stage-artifacts.sh` and restart
the container — no rebuild needed. Only the staged files are exposed under
`/output/` (no NAS, no listing of other renders).

## Share it over Tailscale

The stdlib server has **no auth and no TLS**, so keep it on your private tailnet
(don't enable Tailscale Funnel / a public tunnel for this image).

Option A — Tailscale Serve (HTTPS + a clean name; recommended):
```bash
tailscale serve --bg 8080          # → https://<your-machine>.<tailnet>.ts.net
tailscale serve status             # show the mapping
tailscale serve --https=443 off    # tear it down
```

Option B — reach the container port directly on the tailnet:
```bash
tailscale ip -4                    # your laptop's 100.x.y.z tailnet IP
# testers open  http://100.x.y.z:8080/
```

Testers must be signed in to the same tailnet (and it must be sharing-enabled).

## Live renders (out of scope for this image)

Triggering real renders from the browser needs `serve.py` in a **GDAL** base
image (`geopandas`/`pyogrio`/`rasterio`) with `datasets/` and `cache/` mounted as
volumes (~13 GB for Oregon alone), plus `resvg`/`rsvg-convert` + `assets/fonts/`
for the print/museum styles. That's a separate, much larger service — add it here
if testers need to generate art rather than review it.
