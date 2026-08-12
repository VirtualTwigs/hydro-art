# Task Breakdown: Web Control Surface

## Status

Direction chosen (2026-08-10): Prototype A + Prototype B's month timeline. The shared foundation
(`web/shared/ux.css`, `web/shared/hydro-ux.js`) and three prototypes exist; Prototype A was
switched to B's timeline and then promoted to the canonical `web/studio.html`. All three open
decisions in `planning/requirements.md` (preview fidelity, output-contract shape, proposed-flag
surfacing) are resolved (see `implementation/report.md`). Because #23–#25 have since shipped, the
mapping helpers now emit those as real `build.py` flags (with honest caveats for the two options
that still fail fast in the 2D pipeline).

## Task Group 1: Shared foundation hardening

- [x] Confirm `web/shared/hydro-ux.js` option data matches the pipeline: `STATES` vs
  `src/config.SUPPORTED_REGIONS`, `COUNTIES` rosters, `PALETTES.neon` vs `src/coloring.PALETTES`,
  `HUC_LEVELS`, `MONTH_ABBR`. Added source-pointer comments at the `MONTH_ABBR`/`HUC_LEVELS` blocks.
- [x] Verify the mapping helpers (`cliMapping`/`yamlMapping`) emit shipped #23–#25 flags as real
  (`--color-by`/`--width-by`, `--county`, `--months`), with honest caveat notes only for the two
  options that still fail fast in the 2D pipeline (`color_by=elevation`, non-annual `--months`);
  added `mappingSelfCheck(state)` asserting both renderings reference the same selections.
- [x] Node `--check` the shared JS as a repeatable smoke step (documented in the report's
  verification approach).

## Task Group 2: Control surface (Prototype A + B timeline)

- [x] Promote `web/proto-a-studio.html` to the canonical control surface `web/studio.html`
  (name decided with the user); keeps it on the shared CSS/JS with no duplicated
  tokens/engine/option data.
- [x] Wire all controls through the single `state` object → `applyStyles()` + mapping (geography,
  scope+county, time via B's timeline, color modes, width modes, glow), each updating the preview
  live.
- [x] Add the degenerate-width warning behavior and the proposed-flag surfacing chosen in the open
  decisions (active-but-tagged — decision 3).
- [x] Add real-exported-SVG preview source (decision 1): `file://`-safe file picker alongside the
  procedural default.

## Task Group 3: Output contract

- [x] Finalize the output-contract shape per the resolved open decision: **build.py command +
  config.yaml fragment** (JSON envelope deferred to #27).
- [x] Ensure determinism: identical `state` selections produce identical CLI/YAML text (pure
  functions of `state`; no randomness in the mapping helpers).
- [x] Provide copy affordances for the emitted command/config (CLI/YAML toggle + Copy button).

## Task Group 4: Verification & docs

- [x] Headless syntax check (Node `--check`) of the shared JS and the page's inline script — both pass.
- [~] Manual browser smoke test — attempted Chrome automation (per user), but
  `tabs_context_mcp` reported no Chrome extension connected, so live-DOM interaction was not
  exercisable here. Substituted a headless Node determinism check of the mapping helpers: identical
  `state` yields identical CLI/YAML text and `mappingSelfCheck` returns `{ok:true}`. Live-DOM
  acceptance criteria still need a manual browser pass.
- [x] Update `web/`-related notes in `CLAUDE.md` (web prototypes → control surface) and `HANDOFF.md`
  to reflect the chosen direction, shared foundation, and `web/studio.html` as canonical.

## Verification gates

1. Preview updates live for every control, with no server/datasets, opened over `file://`.
2. State→county repopulation and county re-scope are visible in the preview.
3. Month range drives both preview (fixed year-max width scale) and the output contract.
4. Emitted `build.py` command and `config.yaml` are deterministic, mutually consistent, and mark
   proposed-only options.
5. No duplicated CSS tokens / option data / preview engine / mapping logic across `web/`; `src/` and
   the offline suite have no dependency on `web/`.
