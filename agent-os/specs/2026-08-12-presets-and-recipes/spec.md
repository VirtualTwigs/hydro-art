# Spec — Presets & shareable render recipes (roadmap #28)

## Summary

Add a **recipe** layer to the control surface: a canonical, serializable subset of
`state` that captures exactly the reproducible art-direction selections, plus pure
helpers to encode/decode/sanitize/apply it, a small **named-preset** catalog, and a
"Copy share link" / `location.hash` restore path. All logic lives in
`web/shared/hydro-ux.js` (pure, deterministic, `file://`-safe, testable headlessly in
Node). `studio.html` only wires UI to the helpers.

## The recipe

A recipe is the subset of `state` that is *reproducible art direction*. Preview-only
fields are excluded:

Included (`RECIPE_KEYS`):
`state, scope, county, huc, timeMode, monthStart, monthEnd, colorMode, palette, single,
bg, widthMode, minW, maxW, gamma, glow, glowR`

Excluded (preview-only / derived): `previewSource, loadedName, month, _nudge`.

`toRecipe(state)` → a plain object with exactly `RECIPE_KEYS`, in canonical key order.

## Helpers (all in `hydro-ux.js`, all pure)

- `toRecipe(state)` → canonical recipe object (only `RECIPE_KEYS`, fixed order).
- `sanitizeRecipe(obj)` → a recipe with every field validated/clamped against the same
  catalogs the UX uses, or `null` if `obj` is not a usable object. Unknown keys dropped;
  missing keys filled from a canonical default recipe. Validation rules:
  - `state` ∈ `STATES` keys, else default.
  - `scope` ∈ `{state, county}`.
  - `county`: if `scope==="county"`, must be in `COUNTIES[state]` (else first county);
    if `scope==="state"`, forced `null`.
  - `huc` ∈ `HUC_LEVELS` keys.
  - `timeMode` ∈ `{annual, single, range}`.
  - `monthStart`/`monthEnd` integers clamped to `0..11`.
  - `colorMode` ∈ `{watershed, single, elevation}`.
  - `palette` ∈ `PALETTES` keys.
  - `single`/`bg` valid `#rrggbb` hex (else default).
  - `widthMode` ∈ `{flow, uniform}`.
  - `minW`/`maxW`/`gamma`/`glowR` finite numbers clamped to sane ranges.
  - `glow` coerced to boolean.
- `encodeRecipe(state)` → URL-safe string: `b64url(JSON.stringify(toRecipe(state)))`.
- `decodeRecipe(str)` → `sanitizeRecipe(JSON.parse(b64urlDecode(str)))` or `null` on any
  parse/format failure (never throws).
- `applyRecipe(state, recipe)` → returns a new `state` with the sanitized recipe merged
  over it (preview-only fields preserved from the incoming `state`).
- `PRESETS` → ordered array of `{id, label, kind, recipe}` where `recipe` is a partial
  recipe merged over the current selection; `kind` ∈ `{state, county, print, screen}`.
- `presetById(id)` → the preset entry or `null`.
- `applyPreset(state, id)` → `applyRecipe(state, presetById(id).recipe)` (partial recipe
  merged over current state), or unchanged `state` if unknown id.

### base64url primitives

`b64url`/`b64urlDecode` use `btoa`/`atob` when present (browser) and fall back to
`Buffer` (Node) so the round-trip is identical in both and testable headlessly. URL-safe
alphabet (`+`→`-`, `/`→`_`, strip `=`).

## Round-trip contract

For any `state`, `decodeRecipe(encodeRecipe(state))` deep-equals `toRecipe(state)`
(because `toRecipe` already produces only sanitized-domain values for a valid state).
`decodeRecipe` of garbage returns `null`. Determinism: same input → same string.

## Named presets (initial catalog)

- `or-screen` — "Oregon · screen": Oregon, whole-state, watershed/neon, flow widths, glow
  off. (kind: state)
- `clark-print` — "Clark County · print": Washington, county=Clark, watershed/ice,
  uniform widths, glow off, print-leaning bg. (kind: county)
- `print-mono` — "Print · elevation": colorMode elevation, dark bg, flow widths. (kind:
  print)
- `screen-glow` — "Screen · neon glow": watershed/neon, glow on. (kind: screen)

These are partial recipes merged over the current selection (e.g. `screen-glow` only sets
color/glow, leaving geography as-is), except the two geographic presets which set
state/scope/county explicitly.

## studio.html wiring

- **Presets fieldset**: a row of buttons (one per `PRESETS` entry) that call
  `applyPreset(state, id)` then `syncControls()` + `rebuild()`.
- **`syncControls()`**: a new function that pushes the whole `state` back onto every DOM
  control (selects, segmented buttons, ranges + their value labels, glow toggle,
  timeline) so a preset/recipe apply is reflected everywhere. Existing per-control change
  handlers stay; `syncControls` is the reverse direction (state → DOM).
- **"Copy share link"** button: writes `#` + `encodeRecipe(state)` to `location.hash`
  and copies `location.href` to the clipboard (best-effort; falls back to just setting
  the hash).
- **Boot restore**: on load, if `location.hash` holds a recipe, `decodeRecipe` it and, if
  non-null, `applyRecipe` before the first `rebuild()`; then `syncControls()`.

## Testing

- New headless Node test file (`tests/test_recipe_roundtrip.mjs` or a `node --check` +
  inline harness) exercising: round-trip deep-equality for several states; `decodeRecipe`
  garbage → null; determinism; sanitize clamps/allowlist rejection; preset partial-merge;
  base64url URL-safety (no `+`/`/`/`=`). Run with the system `node`, no new dependency.
- `node --check web/shared/hydro-ux.js` stays green.

## Out of scope

- Server-side persistence / accounts (recipes are self-contained in the URL).
- Any change to the `build.py`/CLI output contract or live-run behavior from #26/#27.
- Print-export pipeline changes (a "print" preset only sets existing knobs).
