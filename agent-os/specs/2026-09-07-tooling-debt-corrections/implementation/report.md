# Implementation report — Tooling debt corrections (Track C2)

**Date:** 2026-09-07 · **Spec:** `agent-os/specs/2026-09-07-tooling-debt-corrections/`
**Source:** corrections roadmap Track C2 (from Epoch 9/12/Gen-1 retrospectives).

## What shipped

### C2.1 — direct-run `src`-import shim (7 tools + class-wide guard)
Added the canonical shim `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
before the first `src` import in the seven tools that ran as `__main__`, imported `src`, and
lacked it: `acquire_dem.py`, `cache_manifest.py`, `detect_unfinished.py`, `migrate_storage.py`,
`monthly_flow.py`, `package_cache.py`, `update_status.py`. Added `from pathlib import Path` to the
three that didn't already import it (`acquire_dem`, `cache_manifest`, `package_cache`). The shim is
idempotent in module mode, so normal `python -m tools.x` runs are unchanged. `detect_unfinished.py`
is the SessionStart-hook entry point, so this repaired a live workflow that only worked under `-m`.

### C2.2 — pin `ruff`
`pyproject.toml` `[project.optional-dependencies].dev` → `["pytest>=8.0", "ruff>=0.6"]`, so the
configured linter installs from the declared dev extras.

### C2.3 — CWD-independent report caches
Promoted a `REPO = Path(__file__).resolve().parent.parent` constant in `report_common.py` and
`render_state_yoy.py` and anchored every cache/output literal to it: `FIG_DIR`, the `_wshed` clip
cache (`report_common`), and the `_yoy_net` network cache, `_peakcache`, and `output/yoy` frame dir
(`render_state_yoy`). Repo-root-CWD runs resolve to the identical paths (byte-identical); runs under
`jupyter nbconvert` (CWD = notebook dir) no longer miss their caches and fall through to a live WBD
read. The two extra `render_state_yoy` literals (`_peakcache`, `output/yoy`) were surfaced by the
regression test and anchored for consistency.

## Tests (`tests/test_tools_direct_run.py`, +6, TDD)
Pure/offline — reads tool source as text and spawns subprocesses; never imports the heavy tools at
collection time. Written first, confirmed **red** (6 failing) on the pre-fix tree, then green.
- **Unit / static invariants:** `test_direct_run_tools_have_src_import_shim` (all 46 tools — a shim
  must precede the first `src` import), `test_report_caches_are_repo_anchored` (no bare CWD-relative
  cache/figure literal; paths reference `REPO`), `test_ruff_pinned_in_dev_extras`.
- **Integration / e2e:** `test_pure_tools_run_as_script_from_foreign_cwd` — runs
  `detect_unfinished.py --help` and `update_status.py --help` as real subprocesses from a tmp CWD;
  asserts exit 0 and no `ModuleNotFoundError`. This reproduces the exact bug end-to-end. The other
  five fixed tools pull GDAL/numpy at import and are covered by the static invariant only (see
  `planning/watch-list.md`).
- **Automated:** all run under the standard `pytest`, so CI exercises them.

## Regression / invariants
- Full offline suite: **890 passed** (884 baseline + 6 new). `py_compile` OK on all 9 edited tools.
- **No `src/` edit, no `PIPELINE_STAGES` edit** → 2D default render byte-identical.
- Extra proof: `package_cache.py --help` runs cleanly from `/tmp` (exit 0, 0 `ModuleNotFoundError`).

## Not done (honest carry-forward)
- The C2.3 real-data confirmation — that a `jupyter nbconvert` report run actually reuses the caches
  instead of a live WBD read — needs a GDAL+NAS notebook host and stays a **Track C4** follow-up. The
  offline change is verified structurally (REPO-anchored) and by the repo-root byte-identity argument.
- Only C2 of the corrections roadmap is done; C1/C3 remain (one item at a time).
