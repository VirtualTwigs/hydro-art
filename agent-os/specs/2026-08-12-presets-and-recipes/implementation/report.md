# Implementation report — Presets & shareable render recipes (roadmap #28)

## What shipped

A **recipe** layer on the control surface: a canonical, serializable subset of the
studio's `state` capturing exactly the reproducible art-direction selections, plus pure
encode/decode/sanitize/apply helpers, a named-preset catalog, and a "Copy share link" /
`location.hash` restore path. This closes Epoch 6.

All logic is pure and lives in `web/shared/hydro-ux.js`; `web/studio.html` only wires UI
to it. Everything is `file://`-safe (no build, no server, no new dependency) and testable
headlessly in Node.

## Changes

### `web/shared/hydro-ux.js` (recipe engine)

- `RECIPE_KEYS` (17 keys) + `DEFAULT_RECIPE` — the canonical, ordered recipe shape.
  Preview-only fields (`previewSource`, `loadedName`, derived `month`, RNG `_nudge`) are
  deliberately excluded.
- `toRecipe(state)` → canonical, sanitized recipe (drops preview-only fields).
- `sanitizeRecipe(obj)` → full recipe with every field validated/clamped against the same
  catalogs the UX uses (`STATES`, `COUNTIES`, `PALETTES`, `HUC_LEVELS`, mode allowlists,
  `#rrggbb` hex, numeric clamps); missing keys filled from defaults; county reconciled
  with scope/state; `null` for non-objects. A shared/hand-edited link can never inject
  invalid state.
- `encodeRecipe(state)` / `decodeRecipe(str)` — base64url of the recipe JSON.
  `decodeRecipe` never throws (returns `null` on any garbage). Round-trips exactly:
  `decodeRecipe(encodeRecipe(s))` deep-equals `toRecipe(s)`.
- `b64url` / `b64urlDecode` — `btoa`/`atob` in the browser with a `Buffer` fallback in
  Node, so the round-trip is identical in both and headlessly testable. URL-safe alphabet
  (no `+` `/` `=`).
- `applyRecipe(state, recipe)` — merges a (possibly partial) recipe onto a live state,
  validating each present key, preserving preview-only fields, and reconciling
  county/scope. Absent keys are left untouched, so partial presets change only what they
  name.
- `PRESETS` (`or-screen`, `clark-print`, `print-mono`, `screen-glow`) +
  `presetById(id)` + `applyPreset(state, id)`.
- Module made Node-loadable: the IIFE now resolves `window`→`globalThis`→`this`, and
  exports `module.exports = HydroUX` when running under CommonJS.

### `web/studio.html` (UI wiring)

- **Presets & sharing** fieldset: buttons generated from `HydroUX.PRESETS` (apply →
  `syncControls()` → `rebuild()`) and a **⧉ Copy share link** button that writes
  `encodeRecipe(state)` into `location.hash` and copies `location.href`.
- `syncControls()` — the reverse of the per-control change handlers: pushes the whole
  `state` back onto every DOM control (selects, segmented buttons, ranges + value labels,
  glow toggle, timeline) so a preset/recipe apply is reflected everywhere. Range value
  formatters were factored into a shared `FMT` map reused by both `bindRange` and
  `syncControls`. `fillCounties` was split into `renderCountyOptions()` (options only) +
  the state-resetting `fillCounties()` so sync can repopulate without clobbering
  `state.county`.
- Boot restore: `restoreFromHash()` decodes a recipe from `location.hash` and
  `applyRecipe`s it before the first `rebuild()`; boot then `syncControls()`.

## Tests

- `tests/test_recipe_roundtrip.cjs` (NEW, 11 headless Node tests, stdlib `node` only):
  `toRecipe` drops preview-only keys; round-trip deep-equality across 8 states;
  determinism; base64url URL-safety; `decodeRecipe` garbage → `null`; sanitize
  clamp/allowlist; non-object → `null`; county/scope coherence; preset partial-merge;
  unknown-preset no-op; `applyRecipe` preserves preview-only fields.

## Verification

- `node --check web/shared/hydro-ux.js` — clean.
- `node tests/test_recipe_roundtrip.cjs` — 11/11 pass.
- Inline `web/studio.html` script parses clean (`node --check` on the extracted script).
- Full Python suite: **361 passed** (unchanged — `src/` and the offline suite keep no
  dependency on `web/`).

## Caveats / not done

- **Live `file://` browser smoke was not run**: the Claude-in-Chrome extension was not
  connected in this session. The pure recipe logic and the inline-script syntax are
  verified headlessly, but the DOM wiring (`syncControls`, preset buttons, hash restore)
  was not exercised in a live browser. Recommend a manual pass: apply a preset, copy the
  link, reload from the hash, confirm every control reflects the recipe.

## Out of scope (unchanged)

- Server-side persistence / accounts (recipes are self-contained in the URL).
- No change to the `build.py`/CLI output contract or the #27 live-run behavior.
- Print-export pipeline changes (a "print" preset only sets existing knobs).
