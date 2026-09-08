# End-to-End Walkthrough — Produce Your First Image

A hands-on manual test of the **live** path: fill out the Studio form → a job is
submitted → the pipeline processes it off-thread → an image comes back in the
browser. This is the `serve.py` + `web/studio.html` flow (roadmap #27).

Where the big-picture roles/products live: `docs/operations-and-customer-guide.md`.
This doc is narrower: *do these steps and get one rendered river map on screen.*

---

## The flow at a glance

```
 web/studio.html            src/server.py           src/jobs.py            src/pipeline.py
 ───────────────            ─────────────           ──────────            ────────────────
 fill the form
 click "▶ Run pipeline"
   │  H.renderRequest(state)  → structured JSON (real src/config keys)
   ▼
 POST /api/render ─────────► handle_request
                              runner.submit(payload) ─► settings_from_payload
                                                         build_settings()  (validate at boundary)
                                                         Job(PENDING) registered
                                                         executor.submit(_run) ──► off-thread
                              202 {"job": "<id>"}                                   pipeline.run(settings)
   ◄──────────────────────── job id                                                12 ordered stages
   │                                                                               download→…→export
   │  poll every 1s
   ▼
 GET /api/jobs/<id> ───────► job status envelope
   │  {"state":"running"} … then {"state":"succeeded","sha256":…,"outputs":{…}}
   ▼
 GET /api/jobs/<id>/artifact?fmt=svg ─► the produced SVG bytes
   │
   ▼
 SVG shown in the stage + a "download SVG" link
```

Job lifecycle: `pending → running → succeeded` (or `→ failed`, with the error
surfaced in the browser). States are defined in `src/jobs.py`.

---

## Prerequisites (check these once)

1. **Interpreter + GIS stack.** The live pipeline needs the heavy GIS deps
   (unlike the offline test suite).
   ```bash
   .venv/bin/python -c "import geopandas, pyogrio, shapely, numpy, networkx; print('GIS stack OK')"
   ```
   If that fails: `.venv/bin/pip install -r requirements.txt`.

2. **Datasets staged for a zero-download run.** A build downloads *nothing* when
   the HUC4 dir is already extracted (`ensure_cached` short-circuits). These are
   present under `datasets/nhdplus_hr/`:
   - **Washington** → HUC4s `1701 1702 1703 1708 1710 1711`
   - **Oregon** → HUC4s `1707 1708 1709 1710 1712 1801`

   So a **whole-state Washington or Oregon** render runs with no NAS and no
   network. (`REGION_HUC4` in `src/datasets.py` is the mapping.)

3. **Optional exporters** (only needed for PNG/PDF, not for the first SVG):
   `resvg` and `rsvg-convert` — check with `which resvg rsvg-convert`. `svgo` is
   optional and degrades gracefully if absent.

> **County scope needs one extra file.** A `--county` render requires the Census
> `cb_2023_us_county_500k` shapefile staged locally; it is **not** bundled. For
> your first image, use **whole-state** scope (below). Add county later.

---

## Part A — First image via the Studio form  (the form → job → image test)

### 1. Start the local server

```bash
.venv/bin/python serve.py
```

You'll see a storage line and:

```
Control surface: http://127.0.0.1:8765/  (Ctrl-C to stop)
```

The `storage:` line tells you where outputs land (local `output/` unless a NAS or
`--external-root` is mounted). Leave this running.

### 2. Open the control surface

Open **http://127.0.0.1:8765/** in a browser. It serves `web/studio.html`.

> Opening the file directly (`file://…/studio.html`) leaves the **▶ Run pipeline**
> button disabled — the live run only works when served by `serve.py`.

### 3. Fill out the form (first-image-safe choices)

| Control | Set it to | Why |
| --- | --- | --- |
| **Geography → State** | **Washington** (or Oregon) | Datasets are staged; zero downloads. |
| **Geography → Scope** | **Whole state** | County needs the Census shapefile (not bundled). |
| **Group / color by** | HUC4 basin (default) | Default coloring. |
| **Time** | Annual mean | Non-annual months **fail fast** in the 2D pipeline. |
| **Color** | By watershed · palette **neon** | `neon` is the only shipping palette; `elevation` fails fast in 2D. |
| **Line width** | Scale by flow (defaults fine) | Matches the reference maps. |
| **Glow** | Off (or On) | Either works. |

Avoid, for a *first* run, the honest caveats the surface itself flags:
`color_by=elevation`, and any non-annual `--months` — both parse but **fail fast**
in the 2D `build.py`/pipeline (use `tools/render_state_mono.py` /
`tools/render_monthly.py` for those instead).

### 4. Submit the job

Click **▶ Run pipeline**. Under the hood:
- `H.renderRequest(state)` builds a JSON body of real `src/config` keys and
  `POST`s it to `/api/render`.
- The runner validates it through `build_settings` (bad config → HTTP 400 shown
  in the status strip) and returns `202 {"job": "<id>"}`.
- The browser polls `GET /api/jobs/<id>` once a second; the status strip shows
  `Running pipeline… (running)`.

A **whole-state render is large** — expect it to churn through all 12 stages
(clip, build graph, watersheds, color, SVG, export). Watch the `serve.py` console
for stage logging.

### 5. Get the image

On success the page fetches `GET /api/jobs/<id>/artifact?fmt=svg`, draws the SVG
in the stage, shows `✓ Rendered. sha256 …`, and adds a **download SVG** link. The
file is also on disk under the server's `output/` root.

**That's your first image.** The `sha256` is the determinism fingerprint — the
same inputs always produce the same bytes.

---

## Part B — Same render, straight from the CLI (no browser)

The Studio's **Output contract** panel prints the exact `build.py` command for the
current form state (the `Copy` button copies it). The equivalent first-image run:

```bash
.venv/bin/python build.py --region Washington --palette neon --width-by flow
```

Default output is **SVG only** (`src/config.py`: `output = {svg:True, png:False,
pdf:False}`). To also get raster/print formats (needs `resvg`/`rsvg-convert`):

```bash
.venv/bin/python build.py --region Washington --palette neon --glow --output svg png pdf
```

Outputs land under `output/`. This is the same pipeline the served button runs —
the browser path just wraps it in the job lifecycle.

---

## Part C — Produce a Water Story **report** (separate subsystem)

The report is **not** part of the Studio form / job flow. It's a parallel,
offline-friendly subsystem driven by its own tool, rendering figures a viewer page
reads.

```bash
# Defaults render the Salmon Creek (WA) watershed, 1944–1989, nClimGrid climate.
.venv/bin/python tools/build_watershed_report.py

# Or target a watershed explicitly:
.venv/bin/python tools/build_watershed_report.py \
  --huc4 1708 --huc12 170800030102 170800030103 \
  --name "Salmon Creek" --start 1944 --end 1989 --climate-source nclimgrid
```

- Figures are written to `notebooks/figures/` (override with `--out-dir`); a JSON
  summary prints to stdout.
- View them with `web/report.html` (the watershed-report viewer over
  `src/flow_metrics`).
- **Climate rights:** default `nclimgrid` is public-domain and sellable with
  attribution. **Never** ship a `--climate-source prism` report commercially
  (A/B only) — the fulfillment rights gate refuses it.

---

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| **▶ Run pipeline** is greyed out | Page opened over `file://`. Use the `serve.py` URL. |
| `400` / red status on submit | Config rejected at the boundary. Re-read the error; avoid `elevation` color and non-annual months in the 2D path. |
| Job goes `failed` with a missing-file error | Chose **county** scope without the Census `cb_2023_us_county_500k` shapefile, or a region whose HUC4s aren't staged. Use whole-state WA/OR. |
| `ImportError` for geopandas/pyogrio | GIS stack not installed: `.venv/bin/pip install -r requirements.txt`. |
| PNG/PDF missing but SVG fine | `resvg`/`rsvg-convert` not on PATH; the served button only makes SVG anyway. Use `build.py --output …` with the exporters installed. |
| Permission error under `/Volumes/home` | NAS not mounted; `serve.py` falls back to local `cache/`. Or pass `--cache-dir cache`. |
| Render is very slow | Whole-state renders are large. Expected. Watch stage logs in the `serve.py` console. |

---

## Where each piece lives (for when you go deeper)

- **Form + live-run JS:** `web/studio.html`; shared logic `web/shared/hydro-ux.js`
  (`renderRequest`, `cliMapping`, `yamlMapping`).
- **HTTP glue:** `src/server.py` (`handle_request` routes; static file guard).
- **Job lifecycle + validation:** `src/jobs.py` (`JobRunner`, `settings_from_payload`).
- **Entry point wiring the real pipeline:** `serve.py`.
- **The 12-stage pipeline:** `src/pipeline.py` (`PIPELINE_STAGES`).
- **Report subsystem:** `tools/build_watershed_report.py`, `tools/report_common.py`,
  `src/flow_metrics.py`, viewer `web/report.html`.
</content>
</invoke>
