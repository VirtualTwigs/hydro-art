# Specification: Web Control Surface

## Goal

Turn the chosen prototype into a coherent, reusable control surface for composing a hydrographic
render: state → county/whole-state, single month / month range / annual mean, coloring, and
line-thickness — with a faithful live client-side preview and a deterministic, reproducible output
contract (`build.py` command + `config.yaml`). This is roadmap item #26; it consumes the pipeline
capabilities of #23–#25 as a mapping target and does not itself run the pipeline (#27).

Chosen direction: **Prototype A** (`web/proto-a-studio.html`, dense left-rail studio) using
**Prototype B**'s click-to-set month timeline for single/range selection. Both build on the shared
`web/shared/ux.css` + `web/shared/hydro-ux.js` foundation created during prototyping.

## Data flow

```text
option data (states/counties/palettes/HUC/months)   ← mirrors src/config, src/coloring, render_common
  → user selections (a single UX `state` object)
  → live preview        : shared procedural network + seasonal monthly-flow sim → styled SVG
  → output contract     : selections → build.py command + config.yaml fragment
```

The preview and the output contract are driven from the *same* selection object, so what you see
and what you would build never diverge.

## Chosen model

A single mutable `state` object (already used by the prototypes) is the one source of truth:

- geography: `state`, `scope` (`state`|`county`), `county`, `huc` (grouping/color granularity);
- time: `timeMode` (`annual`|`single`|`range`), `monthStart`, `monthEnd`, derived display `month`;
- color: `colorMode` (`watershed`|`single`|`elevation`), `palette`, `single`, `bg`;
- width: `widthMode` (`flow`|`uniform`), `minW`, `maxW`, `gamma`;
- glow: `glow`, `glowR`.

All rendering and mapping are pure functions of this object plus the shared engine. No control
mutates the DOM preview directly; every change routes through `applyStyles()` + the mapping
helpers.

## Control surface (Prototype A layout)

A left rail of `fieldset` sections over a live preview stage, with a pipeline-mapping readout
footer:

- **Geography** — state `<select>`; scope segmented control; county `<select>` (shown when
  scope = county); HUC grouping `<select>`.
- **Time** — `timeMode` segmented control; when not annual, Prototype B's month **timeline**
  (`.timeline`/`.mo`): click a month for single, click both ends for a range; label shows the
  selection.
- **Color** — `colorMode` segmented control; palette `<select>` + swatches (watershed); color
  input (single); hypsometric ramp swatches (elevation); background color input.
- **Line width** — `widthMode` segmented control; min/max/gamma ranges; a live warning line for
  degenerate ranges.
- **Glow** — on/off segmented control; radius range.

## Output contract

Two synchronized, deterministic renderings of the current `state`:

1. **CLI** — a copy-pasteable `build.py` invocation (`HydroUX.cliMapping`).
2. **YAML** — the equivalent `config.yaml` fragment (`HydroUX.yamlMapping`).

Currently-shipped options render as real flags/keys. Options that map to roadmap #23–#25
(`color_by` single/elevation, `width_by` flow min/max/gamma, `--county`, `--months`) render with an
explicit `# (proposed)` / `proposed` marker until those items land, and never appear as if already
supported. When #23–#25 ship, only the mapping helpers change (drop the markers); the UI does not.

## Shared foundation (already established)

- `web/shared/ux.css` — design tokens + components (segmented controls, chips, timeline, stepper,
  glass, swatches). One place for the neon studio look so prototypes/product read as one product.
- `web/shared/hydro-ux.js` — `window.HydroUX`: option data (`STATES`, `COUNTIES`, `PALETTES`,
  `HYPSO`, `HUC_LEVELS`, `MONTH_ABBR`), deterministic preview (`generateNetwork`, `buildSvg`),
  seasonal monthly-flow sim (`seasonalMultiplier`, `yearMaxFlow`) on a fixed year-max scale so
  seasonal swell/retreat is visible, `applyStyles`, and the mapping helpers (`cliMapping`,
  `yamlMapping`, `scopeToken`, `monthsToken`).

Loaded via plain `<link>`/`<script src>` so the surface opens over `file://`.

## Acceptance criteria

1. From one screen a user can set state, scope (county/whole-state), time (single/range/annual via
   B's timeline), color (watershed/single/elevation), line width (flow/uniform + min/max/gamma),
   and glow, and the preview updates live on every change with no server or datasets.
2. Changing state repopulates the county list from that state's real Census roster; selecting a
   county visibly re-scopes the preview.
3. A month range selected on the timeline is reflected in both the preview (month-scaled widths on a
   fixed year-max) and the output contract as a range/animation.
4. The emitted `build.py` command and `config.yaml` fragment are deterministic for a given
   selection and agree with each other; proposed-only options are unambiguously marked.
5. All UI reuses `web/shared/ux.css` + `web/shared/hydro-ux.js`; no duplicated tokens, option data,
   preview engine, or mapping logic across `web/` files.
6. The surface opens directly from the filesystem (`file://`) with no build step, and `src/` and
   the offline test suite remain free of any dependency on `web/`.

## Verification approach

The web surface is outside the Python offline suite. Verify via: (a) a headless syntax check of the
shared JS and each page's inline script (Node `--check`, as used during prototyping); (b) a manual
browser smoke test of the acceptance criteria; (c) determinism spot-checks that identical
selections yield identical CLI/YAML text. Note if the browser cannot be exercised in a given
environment rather than claiming a pass.
