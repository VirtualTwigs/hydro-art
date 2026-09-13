# Alpha customer-journey end-to-end tests (Epoch 24)

Playwright browser tests that walk the **alpha customer site** end to end:
`web/start.html` (landing) → each of the four catalog pages → a **low-resolution proof**
for each product endpoint.

> **This is a non-offline, opt-in harness.** It is deliberately **not** part of the
> Python offline suite (`.venv/bin/python -m pytest`). The proof tests (#97) drive real
> GDAL renders, so they need the GIS stack **and** a pre-extracted county in `datasets/`.
> The landing/navigation tests (#95, #96) run against static delivery alone.

## What it covers

| Spec item | File | Needs GIS/data? |
|-----------|------|-----------------|
| #95 smoke, #96 landing + navigation | `tests/01-landing.spec.js` | No |
| #97 four-endpoint low-res proofs   | `tests/02-endpoints.spec.js` | Yes (skips if `datasets/` empty) |

- **Digital image / poster** → 2D `Pipeline` via `POST /api/render` at the draft
  `png_size` tier (512/1024/2048, Epoch 24 #94) → SVG / PNG proof.
- **Watershed report / animation** → the parallel `tools/` renderers
  (`build_watershed_report.py`, `render_monthly.py`) at low resolution → figure / GIF proof.

## How the server is wired

`playwright.config.js` boots `serve.py --web-root <staged> --port <PORT>`, where `<staged>`
is a real directory (`tests/e2e/.served-root/`, git-ignored) that `global-setup.js` fills
with copies of `web/` **and** `deploy/output/` at config-load time. So `start.html`'s
repo-root-absolute assets (`/web/...`, `/output/...`) **and** the `/api/*` render routes are
served **same-origin**.

Why a staged copy instead of `--web-root .`? `serve.py`'s path-traversal guard resolves
symlinks and refuses anything outside the web root, and the repo's own `output/` is a symlink
to the NAS — so serving the repo root directly makes every `/output/landing/*.webp` **404**,
tripping the landing suite's strict "no console errors" checks. The container deploy sidesteps
this by bind-mounting the real `deploy/output`; the harness mirrors that with the staged root.
Staging runs at **config load** (not the Playwright `globalSetup` hook) because Playwright
awaits the `webServer` readiness probe *before* `globalSetup`, which would 404-timeout.

If a plain `python -m http.server` is running on the same port, stop it first (it has no
`/api`), or set `PORT`/`BASE_URL` (below).

## Prerequisites

- Node 18+.
- Python venv at `.venv/` with the GIS stack installed (`pip install -r requirements.txt`)
  for the #97 proofs. #95/#96 only need `serve.py` importable.
- A pre-extracted county under `datasets/` (the harness targets **Clark County, WA** by
  default — the pipeline's demo county). Downloads are skipped when the dataset dir exists.
- For the two `/api/render` proofs (digital image, poster), the Census cartographic-boundary
  counties shapefile at `/tmp/counties_shp/cb_2023_us_county_500k.shp` (the path
  `src/counties.py` reads). Stage it once — it is **not** committed (public-domain Census
  data, ~12 MB zipped):
  ```bash
  curl -sSL -o /tmp/cb_counties.zip \
    https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip
  unzip -o /tmp/cb_counties.zip -d /tmp/counties_shp
  ```
  Without it the county clip fails; the report/animation proofs don't need it (they
  bbox-clip to Clark's extent via `tools/render_common.CLARK_BBOX_4326`).

## Run

```bash
cd tests/e2e
npm install
npx playwright install chromium   # one-time browser download
npx playwright test               # boots serve.py on :8080, runs the suite
npx playwright test tests/01-landing.spec.js   # landing/nav only (no GIS needed)
```

### Environment knobs

| Var | Default | Meaning |
|-----|---------|---------|
| `PORT` | `8080` | Port the harness starts `serve.py` on. |
| `BASE_URL` | `http://127.0.0.1:$PORT` | Point at an already-running `serve.py` (must expose `/api`); enables `reuseExistingServer`. |
| `PNG_SIZE` | `1024` | Draft raster tier for proofs. Bump (e.g. `4096`) for a final high-res confirmation pass. |
| `HARNESS_REGION` / `HARNESS_COUNTY` | `Washington` / `Clark` | Target place for the proofs. `HARNESS_COUNTY` is the Census `NAME` value (bare, no " County" suffix) — `src/counties.py` matches `NAME`, not `NAMELSAD`. |
| `RENDER_TIMEOUT_MS` | `600000` | Deadline for a `/api/render` proof. Generous on purpose: a Clark County proof measures **~6 min** because `validate` loads the whole Washington region (~2.3M geometries) and repair+reproject over that dominates — the county clip → graph → watersheds → SVG → PNG is only ~13s once reprojected, so the draft tier (which only speeds rasterization) barely helps. |
| `PYTHON` | `.venv/bin/python` | Interpreter used for `serve.py` + the render tools. |

## Notes

- The proof tests assert **presence + basic shape** (a `<svg>`, PNG magic bytes, a figure
  file, a GIF), not byte-equality — byte-level determinism stays the job of
  `tools/verify_determinism.py` and the golden fixtures, so this harness never becomes a
  brittle second golden.
- All proofs come from public-domain USGS sources; nothing here is marked sellable.
- Keep this suite out of `ci.yml`'s offline job. Any CI wiring must be a separate, gated
  job that stages a county first (roadmap #98).
