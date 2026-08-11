# Implementation Report: Web Control Surface

## Resolved open decisions (2026-08-11)

1. **Preview fidelity** → support loading a real exported SVG *in addition to* the procedural
   preview. Procedural stays the default (previews with no datasets/server).
2. **Output contract shape** → emit a `build.py` command + `config.yaml` fragment as the MVP; a
   render-request JSON envelope is deferred to roadmap #27.
3. **Proposed-flag surfacing** → active-but-tagged (proposed controls stay usable and drive the
   preview; their emitted flags/keys are explicitly marked proposed).

## Changes

All work is in `web/proto-a-studio.html` (the chosen base); no changes to `web/shared/*` were
needed — `cliMapping`/`yamlMapping` already existed and are reused as-is.

- **Preview source (decision 1).** New "Preview source" fieldset with a `Procedural | Real SVG…`
  segmented control. "Real SVG…" opens a `file://`-safe `<input type=file>` picker; the chosen
  export is injected into the stage and shown as-is (width/height stripped so it scales). Switching
  back to Procedural rebuilds the deterministic network. A loaded export is display-only — the
  style knobs describe how to *regenerate* it via the output contract, not restyle the loaded file
  (hint text updates to say so).
- **Output contract (decision 2 / Group 3).** Footer now renders both the `build.py` command and
  the `config.yaml` fragment behind a `build.py | config.yaml` toggle, with a Copy button. Both are
  pure functions of the single `state` object.
- **Proposed-flag surfacing (decision 3).** No change required — proposed controls were already
  active and tagged; confirmed the emitted CLI/YAML mark them `(proposed)`.

## Verification

- `node --check web/shared/hydro-ux.js` → pass.
- `node --check` on the extracted page inline script → pass.
- Headless determinism check (Node, loading `hydro-ux.js`): identical `state` yields byte-identical
  CLI and YAML text; `(proposed)` markers present in both.
- **Manual browser smoke test: not exercisable in this environment** (no Chrome extension
  connected). Live-DOM acceptance criteria (live preview updates, state→county repopulation,
  timeline range driving preview widths) still need a manual browser pass.

## CLI paste-runnability fix

`cliMapping` (in `web/shared/hydro-ux.js`) was rewritten so the emitted command is genuinely
paste-runnable. Previously it placed `# (proposed) …` inline comments *before* the trailing ` \`
line-continuation, so the `#` commented out the backslash and broke the multi-line paste. Now only
shipped flags go inside the `\`-continued command (no inline comments), and options mapping to
roadmap #23–#25 are appended as commented-out lines *below* the command — still clearly marked
`(proposed)`, but no longer breaking shell parsing. Verified with `bash -n` on both the shipped-only
and with-proposed renderings, plus a determinism re-check.

## Not done

- Canonical naming/entry for the surface (Group 2 first item) — deferred pending a naming decision
  with the user; work stayed in `proto-a-studio.html`.
- `CLAUDE.md` / `HANDOFF.md` refresh for the control-surface direction (Group 4 last item).
