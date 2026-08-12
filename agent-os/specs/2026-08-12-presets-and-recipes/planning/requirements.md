# Requirements — Presets & shareable render recipes (roadmap #28)

## Problem

The control surface (`web/studio.html`) drives everything from one mutable `state`
object but there's no way to **save**, **share**, or **reproduce** a specific look. #28
adds named presets and an encodable render recipe (URL/JSON) so a look can be captured
and restored exactly — the last item that closes Epoch 6.

## Functional requirements

- **Recipe** — a canonical, serializable subset of `state` capturing exactly the
  reproducible art-direction selections (geography, scope/county, HUC grouping, time,
  color, width, glow). Preview-only fields (procedural vs. loaded source, RNG nudge,
  contract toggle, derived `month`) are **not** part of a recipe.
- **Encode / decode** — `encodeRecipe(state)` → a compact URL-safe string;
  `decodeRecipe(str)` → a sanitized recipe (or `null` on garbage). Round-trips exactly
  for any valid state: `decodeRecipe(encodeRecipe(s))` deep-equals `toRecipe(s)`.
- **Sanitize** — decoding validates every field against the same option catalogs the UX
  uses (`STATES`, `COUNTIES`, `PALETTES`, HUC levels, mode allowlists, hex colors,
  numeric clamps) so a shared/hand-edited link can never inject invalid state.
- **Named presets** — a small catalog of named looks (`state`/`county`/print/screen)
  applied to the current selection; each is a (possibly partial) recipe merged over the
  current state.
- **Apply** — `applyRecipe(state, recipe)` merges a sanitized recipe onto `state`; the
  page then syncs every control and re-renders, so preview + output contract match.
- **Share** — a "Copy share link" action writes the recipe into `location.hash`; on
  load the page restores a recipe found there.

## Non-functional / guardrails

- Pure, deterministic helpers live in `web/shared/hydro-ux.js` alongside the other
  mapping logic; no duplication in the page. `studio.html` only wires UI to them.
- `file://`-safe (no build, no server, no new dependency); passes `node --check`.
- Encoding uses stdlib primitives available in both the browser and Node (`btoa`/`atob`
  with a `Buffer` fallback) so the round-trip is testable headlessly.
- `src/` and the offline Python suite keep **no** dependency on `web/`.

## Out of scope

- Server-side persistence / user accounts (recipes are self-contained in the URL).
- Print-specific export pipeline changes (a "print" preset only sets existing knobs).
- Changing the output-contract or live-run behavior from #26/#27.
