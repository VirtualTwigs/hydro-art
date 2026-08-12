# Implementation Report: Web Control Surface

## Resolved open decisions (2026-08-11; surface promoted to `web/studio.html` 2026-08-12)

1. **Preview fidelity** → support loading a real exported SVG *in addition to* the procedural
   preview. Procedural stays the default (previews with no datasets/server).
2. **Output contract shape** → emit a `build.py` command + `config.yaml` fragment as the MVP; a
   render-request JSON envelope is deferred to roadmap #27.
3. **Proposed-flag surfacing** → active-but-tagged (proposed controls stay usable and drive the
   preview; their emitted flags/keys are explicitly marked proposed).

## Changes

- **Canonical surface.** `web/proto-a-studio.html` was promoted (via `git mv`) to `web/studio.html`
  — the canonical control surface. Title/subtitle updated; the County and Time-legend "proposed"
  tags flipped to "live" (their flags shipped in #24/#25). Still on the shared CSS/JS; no duplicated
  tokens/engine/option data.
- **Preview source (decision 1).** "Preview source" fieldset with a `Procedural | Real SVG…`
  segmented control. "Real SVG…" opens a `file://`-safe `<input type=file>` picker; the chosen
  export is injected into the stage and shown as-is (width/height stripped so it scales). Switching
  back to Procedural rebuilds the deterministic network. A loaded export is display-only — the
  style knobs describe how to *regenerate* it via the output contract, not restyle the loaded file.
- **Output contract (decision 2 / Group 3).** Footer renders both the `build.py` command and
  the `config.yaml` fragment behind a `build.py | config.yaml` toggle, with a Copy button. Both are
  pure functions of the single `state` object.
- **Mapping helpers promoted proposed → real (the substantive #26 change).** Because #23–#25 have
  shipped, `cliMapping`/`yamlMapping` in `web/shared/hydro-ux.js` were rewritten to emit those as
  **real `build.py` flags** (`--color-by`/`--single-color`, `--width-by` + `--width-min/max/gamma`,
  `--county`, `--months`) instead of `(proposed)` markers. Two options are shipped-as-flags but
  still fail fast in the *2D* pipeline and so carry an honest caveat note rather than a clean
  command: `color_by=elevation` (needs the DEM subsystem → `tools/render_state_mono.py`) and
  non-annual `--months` (live month frames land in #27 → `tools/render_monthly.py`). Base
  `line_width`/`background` have no CLI flag and appear only in the YAML fragment. Added
  source-pointer comments at the `MONTH_ABBR`/`HUC_LEVELS` option blocks and a `mappingSelfCheck(state)`
  helper (exported on `window.HydroUX`) that asserts the CLI and YAML renderings reference the same
  core selections and are deterministic.

## Verification

- `node --check web/shared/hydro-ux.js` → pass.
- `node --check` on the extracted `web/studio.html` inline script → pass.
- Headless determinism check (Node, loading `hydro-ux.js`): identical `state` yields byte-identical
  CLI and YAML text; `mappingSelfCheck(state)` returns `{ok:true, issues:[]}`.
- `bash -n` on the emitted shipped-only command (default `state`:
  `--region Oregon --color-by watershed --palette neon --width-by uniform`) → pass; caveat notes
  are appended as commented-out lines below the command, so they don't break the paste.
- **Manual browser smoke test: attempted Chrome automation (per user), but `tabs_context_mcp`
  reported no Chrome extension connected**, so live-DOM interaction was not exercisable here.
  Live-DOM acceptance criteria (live preview updates, state→county repopulation, timeline range
  driving preview widths) still need a manual browser pass.

## CLI paste-runnability

The emitted command is genuinely paste-runnable: only real flags go inside the `\`-continued
command (no inline `#` comments that would comment out the line-continuation), and the honest
caveats for the two still-fail-fast options are appended as commented-out `# notes:` lines *below*
the command. Verified with `bash -n`.

## Not done

- Manual live-DOM browser pass (see Verification) — Chrome extension was not connected.
- Live pipeline execution (running the real generator from the surface) is out of scope here — it's
  roadmap #27.
