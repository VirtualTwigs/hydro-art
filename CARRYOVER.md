# Carry-over — hydro-art

_Written 2026-07-30. Snapshot for the next session. For the durable
per-item workflow and Epoch-1 history see `HANDOFF.md`; this file tracks the
in-flight Epoch 1.5 (waterbody outlines) work and the uncommitted tree._

## TL;DR

- **W1 (waterbody source layers & classification) — committed** as `46a0766`.
- **W2 (waterbody repair/clip/area/selection) — implemented, NOT committed.**
  Waiting on an explicit "commit item W2".
- **W3 (config + CLI + pipeline wiring + no-fill SVG render layers) —
  implemented, NOT committed.** Waiting on an explicit "commit item W3".
- Full suite: **184 passed** (offline, no GDAL/network).
- Next roadmap item: **W4** (geographic QA & regional presets).

## Roadmap position (`agent-os/product/roadmap.md`)

Epoch 1 (items 1–10) complete and committed. Now in **Epoch 1.5 — waterbody
outlines**, four phases W1–W4:

| Item | Phase | State |
|------|-------|-------|
| W1 | 1.5.1 Source layers & classification | committed `46a0766` |
| W2 | 1.5.2 Repair, clip & selection | implemented; **commit pending** |
| W3 | 1.5.3 Layered rendering & config | implemented; **commit pending** |
| W4 | 1.5.4 QA & regional presets | not started |

## Resolved art-direction decisions (apply across W2/W3)

Recorded in `agent-os/specs/2026-07-29-waterbody-outlines/planning/requirements.md`:

1. **Enablement** — waterbody outlines **on by default** (a W3 render concern).
2. **Inland threshold** — `min_inland_area_m2` = **0** (keep every valid inland polygon).
3. **Color** — **single distinct water color**, independent of watershed palette (`color_mode: water`), W3.
4. **Coast** — **conservative**: classify bays/inlets/estuaries but exclude open-ocean
   (SeaOcean) and clip-boundary fragments until a reviewed coastal mode exists.

## What W1 + W2 delivered (library only — not yet wired into the pipeline)

- `src/loading.py` — `WATERBODY_LAYER_ALLOWLIST` (`NHDWaterbody`, `NHDArea`) kept
  separate from the flowline allowlist; `discover_waterbody_layers()`;
  `PyogrioLayerLoader.load_waterbody_layers()` populates `Layer.attributes`.
- `src/waterbodies.py` — `WaterbodyFeature` value object (incl. `area_m2`),
  versioned `FTYPE_CLASS` policy (`WATERBODY_POLICY_VERSION = "2026-07-29.1"`),
  `classify_waterbody()` / `classify_layer()`. Name is secondary-only (bay↔inlet).
- `src/waterbody_selection.py` — `process_waterbodies()` (repair → reproject
  EPSG:5070 → region clip → area → policy, reusing `repair_geometry` /
  `clip_geometry`); `WaterbodySelectionPolicy`; `WaterbodySelection` report
  (every candidate selected or excluded; dedup + `shared_edge_pairs`).

**W1 + W2 default 2D builds are byte-identical** — the library became live in W3.

## What W3 delivered (config + CLI + pipeline wiring + rendering)

- `src/config.py` — `WaterbodySettings` (`Settings.waterbodies`),
  `DEFAULTS["waterbodies"]`, `SUPPORTED_COASTAL_MODES`/`SUPPORTED_RENDER_ORDERS`,
  `_coerce_waterbodies()` boundary validation (tolerates partial mapping).
- `src/cli.py` — `--waterbodies/--no-waterbodies`, `--waterbody-color`,
  `--waterbody-stroke-width`; nested `waterbodies` overrides **deep-merged** so
  YAML < CLI holds per sub-key.
- `src/rendering.py` — `polygon_path_d()` (per-ring closed subpaths, holes +
  multipart) and `_waterbody_lines()`; `render_svg` gained `waterbodies`/
  `waterbody_color`/`waterbody_stroke_width`/`waterbody_order`. `None`/`[]` →
  byte-identical to river-only.
- `src/pipeline.py` — `validate` loads waterbody layers only when enabled AND
  `hasattr(loader, "load_waterbody_layers")`; `generate_svg` classifies →
  `process_waterbodies` (against reprojected `region_boundary`) → renders
  outlines, stashing `WaterbodySelection` in `artifacts["waterbody_selection"]`.
- **Byte-identical default** preserved where there's no areal water (river-only
  loader or `--no-waterbodies`); verified by
  `test_disabled_waterbodies_build_is_byte_identical`.

## Next step for W4 (when asked "create tasks and implement item W4")

Geographic QA against real Clark County / Oregon / Washington samples; approved
state/county/print thresholds + coastal examples; measure SVG size /
rasterization impact and document a detail policy.

## Uncommitted tree — IMPORTANT

`git status` mixes multiple unrelated buckets. Do **not** `git add -A`.

**A. W2 — ready to commit:**
- `src/waterbody_selection.py` (new)
- `tests/test_waterbody_selection.py` (new)
- `src/waterbodies.py` (added `area_m2`)
- `agent-os/specs/2026-07-29-waterbody-outlines/tasks.md` (ticked Task Group 2 — now also TG3)
- `agent-os/specs/2026-07-29-waterbody-outlines/implementation/report.md` (W2 section — now also W3)

**A2. W3 — ready to commit (this session):**
- `src/config.py`, `src/cli.py`, `src/rendering.py`, `src/pipeline.py` (modified)
- `tests/test_waterbody_config.py`, `tests/test_waterbody_rendering.py`,
  `tests/test_waterbody_pipeline.py` (new)
- Shared with W2: the `tasks.md` TG3 ticks + `report.md` W3 section, and this
  `CARRYOVER.md`.

Note: W2 and W3 both touch `src/waterbodies.py`'s neighborhood, `tasks.md`, and
`report.md`. If committing separately, W2 first, then W3; or bundle W2+W3 in one
commit if the user prefers. Stage waterbody files **by name**, never `-A`.

**B. Pre-existing unrelated work (NOT this session; belongs in its own commits):**
- Modified: `CLAUDE.md`, `agent-os/product/roadmap.md` (large restructure),
  `build.py`, `src/clipping.py`, `src/datasets.py`, `src/ordering.py`,
  `tests/test_datasets.py`, `tests/test_export_pipeline.py`, `tests/test_ordering.py`.
- Untracked: `.theia/`, `agent-os/specs/ReferenceImage.png`,
  `agent-os/specs/ReferenceImage2.png`, `tools/overlay_facilities.py`,
  `tools/rasterize_layered.py`, `tools/render_region_clip.py`, `web/index.html`.

**C. Planned-but-unstarted spec:**
- `agent-os/specs/2026-07-29-dem-elevation-and-3d-modeling/` (untracked; Epoch 2+).

### Caveat carried from the W1 commit
The first W1 commit attempt accidentally swept in bucket B (those files were
already staged in the index). It was undone with a non-destructive
`git reset HEAD~1` (no working-tree content lost), which also **unstaged**
bucket B. So B is now unstaged/untracked and must be re-added deliberately when
you commit that work. Always stage waterbody files by name, never `-A`.
