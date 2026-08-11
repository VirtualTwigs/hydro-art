# Task Breakdown: Web Control Surface

## Status

Direction chosen (2026-08-10): Prototype A + Prototype B's month timeline. The shared foundation
(`web/shared/ux.css`, `web/shared/hydro-ux.js`) and three prototypes exist;
`web/proto-a-studio.html` has already been switched to B's timeline. Three open decisions in
`planning/requirements.md` (preview fidelity, output-contract shape, proposed-flag surfacing) should
be resolved before Group 3.

## Task Group 1: Shared foundation hardening

- [ ] Confirm `web/shared/hydro-ux.js` option data matches the pipeline: `STATES` vs
  `src/config.SUPPORTED_REGIONS`, `COUNTIES` rosters, `PALETTES.neon` vs `src/coloring.PALETTES`,
  `HUC_LEVELS`, `MONTH_ABBR`. Add a short comment pointer at each block to its Python source.
- [ ] Verify the mapping helpers (`cliMapping`/`yamlMapping`) only emit shipped flags as real and
  tag everything mapping to roadmap #23–#25 as proposed; add a tiny self-check that both renderings
  reference the same selections.
- [ ] Node `--check` the shared JS as a repeatable smoke step (document the command in the spec's
  verification approach).

## Task Group 2: Control surface (Prototype A + B timeline)

- [ ] Promote `web/proto-a-studio.html` to the canonical control surface (naming/entry decided with
  the user); keep it on the shared CSS/JS with no duplicated tokens/engine/option data.
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
- [~] Manual browser smoke test — **not exercisable in this environment** (no Chrome extension
  connected). Substituted a headless Node determinism check of the mapping helpers: identical
  `state` yields identical CLI/YAML text and proposed flags are tagged. Live-DOM acceptance criteria
  still need a manual browser pass.
- [ ] Update `web/`-related notes in `CLAUDE.md` (web prototypes → control surface) and `HANDOFF.md`
  to reflect the chosen direction and shared foundation.

## Verification gates

1. Preview updates live for every control, with no server/datasets, opened over `file://`.
2. State→county repopulation and county re-scope are visible in the preview.
3. Month range drives both preview (fixed year-max width scale) and the output contract.
4. Emitted `build.py` command and `config.yaml` are deterministic, mutually consistent, and mark
   proposed-only options.
5. No duplicated CSS tokens / option data / preview engine / mapping logic across `web/`; `src/` and
   the offline suite have no dependency on `web/`.
