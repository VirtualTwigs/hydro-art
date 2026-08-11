# Requirements: Web Control Surface

## Source

- User request: a UX to select a state, then optionally drill into a county (or render the whole
  state), choose a single month / month range / annual mean, and set coloring and line-thickness
  options.
- User direction (2026-08-10): pursue **Prototype A** (dense left-rail studio,
  `web/proto-a-studio.html`) using **Prototype B's** click-to-set month timeline for the
  single/range selection. Both were reviewed against three built prototypes.
- Existing assets: `web/proto-a-studio.html` (chosen base, now updated to use B's timeline),
  `web/shared/ux.css` (design tokens/components), `web/shared/hydro-ux.js` (option data, procedural
  preview generator, seasonal monthly-flow simulation, config/CLI mapping). `web/index.html` and
  `web/3d.html` are the prior single-file mockups.

## Problem

The generator's art-direction knobs are spread across `build.py` flags, `config.yaml`, and a set of
ad-hoc `tools/` scripts (`render_county_clip.py`, `render_state_mono.py`, `monthly_flow.py`,
`render_monthly.py`). There is no single surface where a user can compose a full render — geography,
time, color, and thickness — see a faithful preview, and get a deterministic, reproducible build.
The existing `web/` files are exploratory mockups, not a coherent control surface, and each
duplicates its own CSS/JS.

## Functional requirements

1. **State selection.** Offer the pipeline's supported regions (`src/config.SUPPORTED_REGIONS` —
   Oregon, Washington today). Data-driven so a newly supported state appears without a UI rewrite.
2. **Scope selection.** Whole state or a single county in that state. County lists are the real
   Census rosters for the selected state; changing state repopulates counties.
3. **Time selection.** Annual mean, a single month, or a month range. Range/single use Prototype
   B's click-to-set month timeline (click a month; click both ends for a range), with a range
   understood as "one frame per month" for an animation.
4. **Color options.** `color_by` = watershed (palette-driven), single color, or elevation
   (hypsometric tint). Palette picker with swatches for watershed mode; color picker for single;
   ramp preview for elevation. Background color control.
5. **Line-thickness options.** `width_by` = scale-by-flow (min / max / gamma) or uniform. Live
   validation warnings for degenerate ranges (max < min; min too small to survive rasterization).
6. **Glow options.** On/off + radius, matching the current pipeline glow control.
7. **Live preview.** A client-side preview updates immediately on any control change, using the
   shared procedural network and seasonal monthly-flow simulation. No datasets or server required
   to preview.
8. **Reproducible output contract.** From the current selections, produce (a) a ready-to-run
   `build.py` command and (b) an equivalent `config.yaml` fragment. Controls that map to
   not-yet-shipped pipeline flags (roadmap #23–#25) are clearly marked as proposed and never
   silently emitted as if supported.
9. **Shared foundation.** All UI reuses `web/shared/ux.css` and `web/shared/hydro-ux.js`; no
   per-file duplication of tokens, option data, the preview engine, or the mapping helpers.

## Non-functional requirements

- **No build, no server.** Prototypes and the control surface must open over `file://`; use plain
  `<link>`/`<script src>` (not ES modules) so shared code loads without a dev server.
- **Determinism parity.** The preview is a faithful stand-in, but the emitted command/config is the
  single source of truth; identical selections must always yield the identical command/config.
- **Client-side option data mirrors the pipeline.** States, county rosters, palettes, HUC levels,
  and month labels reflect `src/config.py` / `src/coloring.py` / `tools/render_common.py` values.
- **No coupling into `src/`.** The web surface never becomes an import target of `src/` or the test
  suite, which stay GDAL-free and offline.

## Out of scope (this spec)

- Actually running the pipeline from the browser and returning real rendered output (roadmap #27).
- Making the "proposed" color/width/county/month flags real in `src/`/`build.py` (roadmap
  #23–#25); this spec consumes them as a mapping target and marks them proposed.
- Presets and shareable/encodable render recipes (roadmap #28).
- 3D / terrain UX (covered by `web/3d.html` and Epochs 2–4).

## Open decisions — RESOLVED (2026-08-11)

1. **Preview fidelity.** RESOLVED: support **loading a real exported SVG** in addition to the
   procedural preview. Implemented as a `file://`-safe file picker (no dev server required); the
   procedural network stays the default so the surface still previews with no datasets.
2. **Output contract shape.** RESOLVED: emit a **`build.py` command + `config.yaml` fragment** as
   the MVP deliverable; a render-request JSON envelope is deferred to #27. Rationale: #27 is not yet
   specced, so designing its envelope now would be speculative and likely reworked; the CLI/YAML is
   the reproducibility artifact the user needs today and the mapping helpers already exist. When #27
   lands it can wrap the same `state` selection object into whatever envelope it requires.
3. **Proposed-flag surfacing.** RESOLVED: keep proposed controls **active-but-tagged** (current
   prototype behavior); they remain usable and drive the preview, and their emitted flags/keys are
   explicitly marked proposed until #23–#25 land.
