# Tasks — Presets & shareable render recipes (roadmap #28)

## TG1 — Recipe helpers + presets (pure, in `hydro-ux.js`)

- [x] Write headless Node tests first (round-trip deep-equality across states;
      `decodeRecipe` garbage → null; determinism; sanitize clamp/allowlist; base64url is
      URL-safe; preset partial-merge).
- [x] Add `RECIPE_KEYS` + `DEFAULT_RECIPE` (canonical order/defaults).
- [x] Add `b64url` / `b64urlDecode` (btoa/atob with Buffer fallback).
- [x] Add `toRecipe`, `sanitizeRecipe`, `encodeRecipe`, `decodeRecipe`, `applyRecipe`.
- [x] Add `PRESETS`, `presetById`, `applyPreset`.
- [x] Export all of the above on `window.HydroUX` (and CommonMonth-safe for Node).
- [x] Run ONLY the new tests; green.

## TG2 — studio.html preset + share UI

- [x] Add a Presets fieldset (buttons from `PRESETS`) wired to `applyPreset` + refresh.
- [x] Add a "Copy share link" button → `location.hash` = `encodeRecipe(state)` + clipboard.
- [x] Add `syncControls()` (state → every DOM control incl. timeline) and call it after
      preset/recipe apply.
- [x] On boot, restore a recipe from `location.hash` (decode → apply) before first render.

## TG3 — Verify + docs

- [x] `node --check web/shared/hydro-ux.js`; re-run the round-trip tests; browser smoke
      over `file://` (apply a preset, copy link, reload from the hash).
- [x] Write `implementation/report.md`.
- [x] Tick `tasks.md`; mark roadmap #28 `[x]`; update `HANDOFF.md` + `CLAUDE.md`.
- [x] Run the full Python suite (regression check) and report; STOP (commit is separate).
