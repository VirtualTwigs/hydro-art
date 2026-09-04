# Carry-over — Epoch 16 #65 (and session context)

**Written:** 2026-09-03. Read this first if resuming with a cleared context.

## TL;DR — the one pending action

**Item #65 is fully implemented and verified but NOT committed.** The user's last
build instruction was "commit" (= "commit item #65" per CLAUDE.md's explicit
implement-then-commit split). The immediate next step is to create ONE new git
commit for the #65 work — but the working tree also contains unrelated changes,
so **stage specific files only** (list below), do NOT `git add -A`.

## What to commit (scope = #65 only)

Stage exactly these:

- `src/hydro_structures.py` (new) — the taxonomy module
- `src/loading.py` (modified) — NHDLine loader seam only
- `tests/test_hydro_structures.py` (new) — 9 tests
- `tests/test_loading.py` (modified) — +4 NHDLine seam tests
- `agent-os/specs/2026-09-03-hydro-structure-taxonomy/` (new spec folder — planning/, spec.md, tasks.md, orchestration.yml, implementation/report.md, this file)
- `agent-os/product/roadmap.md` (modified — ONLY the #65 `[ ]`→`[x]` tick + shipped annotation; verified via `git diff`, it's a clean single-item change)

### Do NOT stage (unrelated pre-existing working-tree noise — confirm with user before touching)

- `notebooks/salmon_creek_yoy.ipynb`, `notebooks/washington_state_report.ipynb` (modified)
- `notebooks/wa_flow_yoy.ipynb`, `notebooks/watershed_analysis.ipynb`, `notebooks/washington_state_report.html`, `notebooks/figures/` (untracked)
- `experiments/`, `market-analysis/` (untracked — storefront/market exploration, not #65)
- `tools/extract_preview_geo.py` (untracked — unrelated)
- `.claude/scheduled_tasks.lock` (runtime lock)

### Suggested commit message

```
feat(hydro-structures): FType taxonomy + NHDLine loader seam (Epoch 16 #65)

Add src/hydro_structures.py — a versioned, FType-driven taxonomy classifying
engineered-water NHD structures (dam_weir/gate/lock_chamber/gaging_station/
water_intake_outflow/spillway/canal_ditch/excluded) across NHDLine/NHDPoint/
NHDArea from one policy table. Mirrors src/point_features.py: name-only-refining,
missing FType -> excluded + missing_ftype QA flag, full provenance, no geometry
math, no top-level GDAL imports. Extend src/loading.py with the NHDLine seam
(LINE_LAYER_ALLOWLIST, LINE_ATTRIBUTE_FIELDS, discover_line_layers,
load_line_features). Complementary to waterbodies/point/areal taxonomies
(included codes disjoint, tested). Taxonomy + loader only — no rendering, no
pipeline wiring; default build stays byte-identical.

Co-Authored-By: Claude Opus 4 <noreply@anthropic.com>
```

Follow CLAUDE.md git protocol: new commit (never amend), HEREDOC message, run
`git status` after to confirm.

## What #65 delivered (verified)

- **`src/hydro_structures.py`** — `HYDRO_STRUCTURE_POLICY_VERSION = "2026-09-03.1"`;
  classes `dam_weir, gate, lock_chamber, gaging_station, water_intake_outflow,
  spillway, canal_ditch, excluded`; `HYDRO_STRUCTURE_FTYPE_CLASS =
  {343:dam_weir, 369:gate, 398:lock_chamber, 367:gaging_station,
  485:water_intake_outflow, 455:spillway, 336:canal_ditch}`. `436 Reservoir`
  deliberately excluded (waterbodies owns it). Frozen `HydroStructure` dataclass,
  `classify_hydro_structure` / `classify_hydro_structure_layer`.
- **`src/loading.py`** — NHDLine seam added; NHDPoint (Epoch 15 `load_point_features`)
  and NHDArea (Epoch 1.5 `load_waterbody_layers`) already load the needed attributes,
  so no new point/area loader.
- **FType codes domain-verified** against real GDB HUC4 1807 (decode embedded
  `NHDFCode` domain table, not memory). Confirmed: 343/336/455/485/367. Flagged
  **UNCONFIRMED** in docstring: `398 lock_chamber` (absent from coastal 1807) and
  `369 gate` on line/area (only confirmed on NHDPoint). Details in
  `planning/group0-findings.md`.
- **Verification:** 761 offline tests pass; default build byte-identical
  (`tools/verify_determinism.py --region Oregon`, 0 structures in default path);
  `src.hydro_structures` pulls no GDAL into `sys.modules`; complementarity proven —
  structure `{343,336,455,485,367,369,398}` disjoint from waterbodies
  `{390,436,493,312}`, point `{458,487,431}`, areal `{466,361,378}`.

Full detail: `implementation/report.md` in this folder.

## Session context beyond #65

### Product direction (saved to memory)
- The user runs **Runde Strategies** (WA consultancy). Long-term goal: public
  website + example catalog + ordering (digital/print/animation/report) + buyer
  guides. Revenue-first gating; sell only public-domain sources.
  → `memory/project_runde_strategies.md`
- **Product-first decision:** deepen the art engine / feature layers FIRST. The
  storefront/intake/checkout/presentation layer is considered "outsourceable" —
  build it later. → `memory/feedback_product_first.md`
- This is why we went straight into Epoch 16 (product frontier) instead of the
  Epoch 11.5 revenue-loop or website work.

### Roadmap staleness discovered (worth tidying later, not yet requested)
- **Epoch 15** (natural water features) and **Epoch 18** (width presets) are
  essentially **code-complete** despite stale `[ ]`/proposed markers. Epoch 16 is
  the true product frontier. Offered to tidy the stale checkboxes; user hasn't
  asked yet.

### Natural next steps in Epoch 16 (offered, not yet requested)
- **#66** — engineered-channel styling on `NHDFlowline` (CanalDitch/Pipeline/ArtificialPath).
- **#67** — structure symbology & rendering + the selection/clip step (the item
  that makes #65 visible).
- **#68** — QA, presets, config settings, CLI flags.
- Also: confirm `398 LockChamber` + line/area `369 Gate` against a lock-bearing HUC4.

## Ground rules that governed this work (keep following)
- Agent OS spec-driven: "create tasks and implement item #N" ≠ "commit item #N"
  (commit is always separate & explicit — never commit unprompted).
- Offline-suite discipline: no top-level GDAL imports in `src/`/`tests/`; every
  `src/<name>.py` has `tests/test_<name>.py`; run only relevant tests per group,
  full suite at end.
- Byte-identical default output (verify with `tools/verify_determinism.py`).
- `INTERNAL_CRS` from `src/crs.py` — never inline `"EPSG:5070"`.
- Rights gate: public-domain sources only (USGS NHD/NHDPlus/WBD, NOAA nClimGrid);
  never sell PRISM-derived assets.
