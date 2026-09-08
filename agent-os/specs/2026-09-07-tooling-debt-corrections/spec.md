# Spec — Tooling debt corrections (Track C2)

## Goal
Close the three recurring tooling-debt items from Track C2 so that (a) any `tools/` script runs
correctly whether invoked as `python -m tools.x` or `python tools/x.py` from any CWD, (b) the
configured linter installs from the declared dev extras, and (c) the watershed-report caches resolve
regardless of CWD. Add offline regression tests so none of the three can silently return.

## Design

### C2.1 — Shim the 7 direct-run tools + class-wide guard
For each of `acquire_dem`, `cache_manifest`, `detect_unfinished`, `migrate_storage`,
`monthly_flow`, `package_cache`, `update_status`:
- Ensure `from pathlib import Path` is imported (add where missing).
- Immediately before the first `from src` / `import src` line, insert the canonical shim:
  `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`.
- Match the existing style (a short `# Make the repo root importable when run as a script.` comment,
  consistent with the 31 tools that already have it where they comment it).

The shim is idempotent and harmless in module mode (repo root is already on `sys.path`; inserting it
again at index 0 changes nothing observable). No behavior change for the normal invocation.

### C2.2 — Pin ruff
`pyproject.toml`: `[project.optional-dependencies] dev = ["pytest>=8.0", "ruff>=0.6"]`. Lower bound
chosen to be recent enough for the configured `line-length` semantics; no upper pin (dev tool).

### C2.3 — REPO-anchored report caches
In `tools/report_common.py` add `REPO = Path(__file__).resolve().parent.parent` (the shim already
computes this inline — promote it to a named constant) and rewrite:
- `FIG_DIR = REPO / "notebooks" / "figures"`
- `clip_cache = REPO / "output" / f"_wshed_{tag}_mo{min_order}.pkl"`
In `tools/render_state_yoy.py`, anchor the network cache the same way:
- `cache = REPO / "output" / f"_yoy_net_{code}.pkl"` (add the `REPO` constant there too).
Repo-root-CWD runs are byte-identical (same resolved paths); foreign-CWD runs are now correct.

## Test strategy (TDD — tests first, must fail red on today's tree)

New module `tests/test_tools_direct_run.py` — pure/offline; reads tool source as **text** and spawns
subprocesses; never imports the heavy tools at collection time.

**Unit (static-analysis invariants):**
1. `test_direct_run_tools_have_src_import_shim` — for every `tools/*.py` that contains
   `if __name__ == "__main__"` and a `from src`/`import src` statement, assert a `sys.path.insert`
   line appears at a lower line number than the first `src` import. Covers all 46 tools (regression
   guard for the whole class, not just the 7).
2. `test_report_caches_are_repo_anchored` — assert `report_common.py` and `render_state_yoy.py`
   contain no bare CWD-relative cache/figure literal (`Path("notebooks/...")`,
   `Path("output/...")`, `Path(f"output/...")`); the figure/cache paths must reference a `REPO`
   anchor.
3. `test_ruff_pinned_in_dev_extras` — parse `pyproject.toml`; assert a `ruff` entry exists in
   `[project.optional-dependencies].dev`.

**Integration / e2e (real invocation, automated in the suite):**
4. `test_pure_tools_run_as_script_from_foreign_cwd` — parametrized over `detect_unfinished.py` and
   `update_status.py`: `subprocess.run([sys.executable, <abs tool path>, "--help"], cwd=<tmp_path>)`
   with a clean env (no injected `PYTHONPATH`); assert `returncode == 0` and
   `"ModuleNotFoundError"` not in stderr. This is the exact bug reproduced end-to-end (it fails red
   today because the shim is missing) and the direct proof the fix works from a foreign CWD.

All four run under the existing offline `pytest` and therefore in CI automatically (the "automated"
leg). No subprocess touches GDAL/numpy (the two chosen tools are stdlib+pure-`src` only).

## Non-goals / invariants
- No `src/` change, no `PIPELINE_STAGES` change → default render byte-identical.
- No new tool behavior; `--help` output and normal runs unchanged.
- The nbconvert real-data confirmation for C2.3 stays a Track-C4 host-gated follow-up (documented,
  not claimed).
